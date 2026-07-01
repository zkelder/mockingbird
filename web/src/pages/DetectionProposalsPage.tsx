import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  CameraSource,
  DetectionProposal,
  DetectionProposalDecision,
  DetectionProposalDecisionResult,
  DetectionProposalStatus,
  MediaAsset,
  Stream,
  Zone,
} from "../api/types";
import { ConfidenceBar } from "../components/ConfidenceBar";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { ProposalStatusBadge } from "../components/ProposalStatusBadge";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

type ProposalFilter = "all" | DetectionProposalStatus;

const proposalFilters: Array<{ value: ProposalFilter; label: string }> = [
  { value: "proposed", label: "Proposed" },
  { value: "converted", label: "Converted" },
  { value: "rejected", label: "Rejected" },
  { value: "accepted", label: "Accepted" },
  { value: "all", label: "All" },
];

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
  const [label, setLabel] = useState("bird");
  const [confidence, setConfidence] = useState("0.72");
  const [suggestedSubjectLabel, setSuggestedSubjectLabel] = useState("unknown_bird");
  const [suggestedSpecies, setSuggestedSpecies] = useState("");
  const [notes, setNotes] = useState("");
  const [generatedProposal, setGeneratedProposal] = useState<DetectionProposal | null>(null);
  const [result, setResult] = useState<DetectionProposalDecisionResult | null>(null);
  const [proposalFilter, setProposalFilter] = useState<ProposalFilter>("proposed");
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
  const selectedStream = selectedMedia ? streamById.get(selectedMedia.stream_id) ?? null : null;
  const selectedSourceName = selectedStream ? sourceNames.get(selectedStream.source_id) : null;
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

  async function submitDemoProposal(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedMedia) {
      setError("Import local media before generating a demo proposal.");
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
    setGeneratedProposal(null);
    try {
      const demoResult = await apiClient.createDemoDetectionRun({
        media_asset_id: selectedMedia.id,
        zone_id: selectedZoneId || undefined,
        label: label.trim() || "bird",
        confidence: parsedConfidence,
        suggested_subject_label: suggestedSubjectLabel.trim() || "unknown_bird",
        suggested_species: suggestedSpecies.trim() || undefined,
        notes: notes.trim() || undefined,
      });
      const proposal = demoResult.proposals[0] ?? null;
      setGeneratedProposal(proposal);
      setProposalFilter("proposed");
      setMessage(
        proposal
          ? `Generated demo proposal ${proposal.id}. Review it before it becomes a product event.`
          : "Demo run completed without creating proposal evidence.",
      );
      setNotes("");
      await loadPageData({ showLoading: false });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Demo proposal could not be generated.");
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
    setGeneratedProposal(null);
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
      setProposalFilter(nextResult.proposal.status);
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
  const proposalCounts = useMemo(() => {
    const counts: Record<ProposalFilter, number> = {
      all: proposals.length,
      proposed: 0,
      converted: 0,
      rejected: 0,
      accepted: 0,
    };
    proposals.forEach((proposal) => {
      counts[proposal.status] += 1;
    });
    return counts;
  }, [proposals]);
  const filteredProposals =
    proposalFilter === "all"
      ? sortedProposals
      : sortedProposals.filter((proposal) => proposal.status === proposalFilter);

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Detection pipeline interface"
        title="Detection Proposals"
        description="Generate demo detector proposals from imported media, review them as evidence, then convert or reject them before they affect analytics and exports."
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

      {generatedProposal ? (
        <section className="panel proposal-decision-panel">
          <div>
            <EvidenceBadge label="Demo evidence generated" tone="review" />
            <h2>{formatLabel(generatedProposal.label)} proposal ready</h2>
            <p>
              This simulated detector proposal did not run a real model or inspect media pixels. Convert it only when
              it should become a reviewable event and visit.
            </p>
          </div>
          <div className="detail-actions">
            <button
              className="primary-action"
              disabled={actionId === `${generatedProposal.id}:convert_to_event`}
              onClick={() => void decideProposal(generatedProposal, "convert_to_event")}
            >
              Accept and convert to review
            </button>
            <button
              className="secondary-action"
              disabled={actionId === `${generatedProposal.id}:reject`}
              onClick={() => void decideProposal(generatedProposal, "reject")}
            >
              Reject
            </button>
          </div>
        </section>
      ) : null}

      {result ? (
        <section className="panel proposal-decision-panel">
          <div>
            <EvidenceBadge
              label={result.proposal.status === "rejected" ? "Evidence dismissed" : "Review case created"}
              tone={result.proposal.status === "rejected" ? "quiet" : "review"}
            />
            <h2>{formatLabel(result.proposal.status)} proposal</h2>
            <p>
            {result.proposal.status === "rejected"
                ? "The proposal was dismissed as evidence. No event or visit was created."
                : "A reviewable event and visit now carry this proposal as detection evidence. Human correction still becomes dataset truth."}
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
            {result.visit || result.event ? (
              <button className="secondary-action" onClick={onOpenReview}>
                Review Queue
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
        <form className="panel manual-import-form" onSubmit={submitDemoProposal}>
          <div className="section-heading">
            <h2>Generate demo proposal</h2>
            <EvidenceBadge label="Evidence only" />
          </div>
          <p className="meta-text">
            This simulates detector proposal generation for the product flow. It does not run a real model or inspect
            media pixels.
          </p>
          <div className="import-flow-strip">
            <span>Media asset</span>
            <span>Demo proposal</span>
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
            <span className="field-helper">Choose local media that future detection evidence would reference.</span>
          </label>
          {selectedMedia ? (
            <div className="proposal-selected-media">
              <MediaAssetPreview asset={selectedMedia} compact />
              <div className="proposal-context-strip">
                <span>Stream: {selectedStream?.name ?? selectedMedia.stream_id}</span>
                <span>Source: {selectedSourceName ?? selectedStream?.source_id ?? "local media"}</span>
                <span>Media stays local</span>
              </div>
            </div>
          ) : null}
          <label>
            Zone
            <select
              disabled={!selectedMedia}
              value={selectedZoneId}
              onChange={(event) => setSelectedZoneId(event.target.value)}
            >
              <option value="">Use stream demo zone</option>
              {selectedZones.map((zone) => (
                <option key={zone.id} value={zone.id}>
                  {zone.name} - {formatLabel(zone.zone_type)}
                </option>
              ))}
            </select>
            <span className="field-helper">
              Leave blank to attach a sensible demo zone from the media stream when available.
            </span>
          </label>
          <label>
            Suggested evidence label
            <input value={label} onChange={(event) => setLabel(event.target.value)} />
            <span className="field-helper">This is not truth until a user reviews and corrects the visit.</span>
          </label>
          <label>
            Evidence confidence
            <input
              max="1"
              min="0"
              onChange={(event) => setConfidence(event.target.value)}
              step="0.01"
              type="number"
              value={confidence}
            />
            <span className="field-helper">Use 0 to 1 for demo confidence; it stays evidence only.</span>
          </label>
          <label>
            Suggested subject label
            <input
              value={suggestedSubjectLabel}
              onChange={(event) => setSuggestedSubjectLabel(event.target.value)}
            />
            <span className="field-helper">Subject and species suggestions help start review; corrections win.</span>
          </label>
          <label>
            Suggested species
            <input
              value={suggestedSpecies}
              onChange={(event) => setSuggestedSpecies(event.target.value)}
              placeholder="optional"
            />
            <span className="field-helper">Optional species guess before human confirmation.</span>
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
            {isSubmitting ? "Generating..." : "Generate demo proposal"}
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
          <div className="proposal-status-tabs" aria-label="Proposal status filters">
            {proposalFilters.map((filter) => (
              <button
                className={proposalFilter === filter.value ? "selected" : ""}
                key={filter.value}
                onClick={() => setProposalFilter(filter.value)}
                type="button"
              >
                {filter.label}
                <span>{proposalCounts[filter.value]}</span>
              </button>
            ))}
          </div>
          {isLoading ? <span className="meta-text">Loading detection proposals...</span> : null}
          <div className="media-list detection-proposal-list">
            {filteredProposals.map((proposal) => {
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
                    <ProposalStatusBadge status={proposal.status} />
                  </div>
                  <div className="proposal-truth-strip">
                    <EvidenceBadge label="Detection evidence" />
                    <span>Human correction becomes dataset truth after review.</span>
                  </div>
                  {asset ? <MediaAssetPreview asset={asset} compact /> : null}
                  <ConfidenceBar value={proposal.confidence} />
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
                      <span>Suggested event</span>
                      <strong>{formatLabel(proposal.suggested_event_type)}</strong>
                    </div>
                    <div className="data-row">
                      <span>Suggested subject/species</span>
                      <strong>
                        {formatLabel(proposal.suggested_species ?? proposal.suggested_subject_label)}
                      </strong>
                    </div>
                  </div>
                  {proposal.notes ? <p>{proposal.notes}</p> : null}
                  {proposal.status === "rejected" ? (
                    <div className="proposal-state-note">
                      Proposal dismissed as evidence. No event or visit was created.
                    </div>
                  ) : proposal.event_id || proposal.visit_id ? (
                    <div className="proposal-state-note">
                      Review case created. Correct the visit before using it as dataset truth.
                    </div>
                  ) : null}
                  <div className="detail-actions">
                    {canDecide ? (
                      <>
                        <button
                          className="primary-action"
                          disabled={actionId === `${proposal.id}:convert_to_event`}
                          onClick={() => void decideProposal(proposal, "convert_to_event")}
                        >
                          Accept and convert to review
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
                    {proposal.event_id || proposal.visit_id ? (
                      <button className="secondary-action" onClick={onOpenReview}>
                        Review Queue
                      </button>
                    ) : null}
                  </div>
                </article>
              );
            })}
            {!isLoading && proposals.length === 0 ? (
              <EmptyState
                title="No detection proposals yet"
                description="Import media, generate demo proposal evidence, then convert it into review when it represents outdoor activity."
                action={
                  <button className="secondary-action" onClick={onOpenImport}>
                    Import media
                  </button>
                }
              />
            ) : null}
            {!isLoading && proposals.length > 0 && filteredProposals.length === 0 ? (
              <EmptyState
                title={`No ${formatLabel(proposalFilter)} proposals`}
                description="Switch proposal status filters to inspect evidence that is still proposed, converted into review, or rejected."
              />
            ) : null}
          </div>
        </div>
      </section>
    </div>
  );
}
