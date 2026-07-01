import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type { MediaAsset, ModelAdapter, ModelAdapterRunResult } from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { ProposalStatusBadge } from "../components/ProposalStatusBadge";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

interface ModelAdaptersPageProps {
  onOpenDetectionProposals: () => void;
  onOpenImport: () => void;
  onProposalChanged: () => Promise<void>;
}

export function ModelAdaptersPage({
  onOpenDetectionProposals,
  onOpenImport,
  onProposalChanged,
}: ModelAdaptersPageProps) {
  const [adapters, setAdapters] = useState<ModelAdapter[]>([]);
  const [mediaAssets, setMediaAssets] = useState<MediaAsset[]>([]);
  const [selectedAdapterId, setSelectedAdapterId] = useState("");
  const [selectedMediaId, setSelectedMediaId] = useState("");
  const [requestedLabels, setRequestedLabels] = useState("unknown_bird");
  const [notes, setNotes] = useState("");
  const [result, setResult] = useState<ModelAdapterRunResult | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const adapterById = useMemo(
    () => new Map(adapters.map((adapter) => [adapter.id, adapter])),
    [adapters],
  );
  const mediaById = useMemo(
    () => new Map(mediaAssets.map((asset) => [asset.id, asset])),
    [mediaAssets],
  );
  const selectedAdapter = adapterById.get(selectedAdapterId) ?? null;
  const selectedMedia = mediaById.get(selectedMediaId) ?? null;

  async function loadPageData(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const [nextAdapters, nextMediaAssets] = await Promise.all([
        apiClient.getModelAdapters(),
        apiClient.getMediaAssets(),
      ]);
      setAdapters(nextAdapters);
      setMediaAssets(nextMediaAssets);
      setSelectedAdapterId((current) =>
        current && nextAdapters.some((adapter) => adapter.id === current)
          ? current
          : nextAdapters[0]?.id ?? "",
      );
      setSelectedMediaId((current) =>
        current && nextMediaAssets.some((asset) => asset.id === current)
          ? current
          : nextMediaAssets[0]?.id ?? "",
      );
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Could not load model adapters.");
    } finally {
      if (showLoading) {
        setIsLoading(false);
      }
    }
  }

  useEffect(() => {
    void loadPageData();
  }, []);

  async function submitAdapterRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedAdapter) {
      setError("Choose a model adapter.");
      return;
    }
    if (!selectedMedia) {
      setError("Import local media before running an adapter contract.");
      return;
    }

    const labels = requestedLabels
      .split(",")
      .map((label) => label.trim())
      .filter(Boolean);

    setIsSubmitting(true);
    setError(null);
    setMessage(null);
    setResult(null);
    try {
      const nextResult = await apiClient.runModelAdapter(selectedAdapter.id, {
        adapter_id: selectedAdapter.id,
        media_asset_id: selectedMedia.id,
        requested_labels: labels.length > 0 ? labels : undefined,
        notes: notes.trim() || undefined,
      });
      setResult(nextResult);
      setMessage(
        `${nextResult.proposals.length} proposal${
          nextResult.proposals.length === 1 ? "" : "s"
        } created as evidence only.`,
      );
      await onProposalChanged();
      await loadPageData({ showLoading: false });
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Adapter run could not be created.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Future detector hooks"
        title="Model Adapters"
        description="Model adapters consume product media/context and create proposal evidence. Review and correction remain required before export truth."
        actions={
          <>
            <button className="secondary-action" onClick={onOpenImport}>
              Import Media
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
        <strong>Model adapters create evidence, not truth</strong>
        <span>
          The local-only demo adapter does not inspect media or run a real model. Its proposals stay
          below the product loop until a user converts, reviews, and corrects them.
        </span>
      </section>

      <section className="split-grid">
        <div className="panel adapter-list-panel">
          <div className="section-heading">
            <h2>Available adapters</h2>
            <EvidenceBadge label="Under the product" tone="quiet" />
          </div>
          <div className="adapter-list">
            {adapters.map((adapter) => (
              <button
                className={`adapter-card${selectedAdapterId === adapter.id ? " selected" : ""}`}
                key={adapter.id}
                onClick={() => setSelectedAdapterId(adapter.id)}
                type="button"
              >
                <span className="meta-text">{formatLabel(adapter.kind)}</span>
                <strong>{adapter.name}</strong>
                <span>{adapter.description}</span>
                <div className="adapter-badge-row">
                  <StatusPill
                    label={formatLabel(adapter.status)}
                    tone={adapter.status === "available" ? "good" : "review"}
                  />
                  <EvidenceBadge
                    label={adapter.creates_review_truth ? "Writes truth" : "Evidence only"}
                    tone={adapter.creates_review_truth ? "review" : "truth"}
                  />
                  {adapter.local_only ? <EvidenceBadge label="Local-only demo adapter" tone="quiet" /> : null}
                </div>
                <small>
                  Media: {adapter.supported_media_types.map(formatLabel).join(", ")} · Labels:{" "}
                  {adapter.supported_labels.map(formatLabel).join(", ")}
                </small>
              </button>
            ))}
            {!isLoading && adapters.length === 0 ? (
              <EmptyState
                title="No model adapters available"
                description="Future detector hooks will appear here when contract definitions are available."
              />
            ) : null}
          </div>
        </div>

        <form className="panel adapter-run-form" onSubmit={submitAdapterRun}>
          <div className="section-heading">
            <h2>Run adapter contract</h2>
            <EvidenceBadge label="Proposal evidence only" />
          </div>
          <label>
            Adapter
            <select
              disabled={adapters.length === 0}
              value={selectedAdapterId}
              onChange={(event) => setSelectedAdapterId(event.target.value)}
            >
              {adapters.map((adapter) => (
                <option key={adapter.id} value={adapter.id}>
                  {adapter.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Media asset
            <select
              disabled={mediaAssets.length === 0}
              value={selectedMediaId}
              onChange={(event) => setSelectedMediaId(event.target.value)}
            >
              {mediaAssets.map((asset) => (
                <option key={asset.id} value={asset.id}>
                  {asset.original_filename} · {formatLabel(asset.media_type)}
                </option>
              ))}
            </select>
          </label>
          {selectedMedia ? <MediaAssetPreview asset={selectedMedia} compact /> : null}
          <label>
            Requested labels
            <input
              value={requestedLabels}
              onChange={(event) => setRequestedLabels(event.target.value)}
              placeholder="unknown_bird, bird, squirrel"
            />
            <span className="field-helper">
              Comma-separated evidence suggestions. Corrected labels remain dataset truth.
            </span>
          </label>
          <label>
            Notes
            <textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="optional adapter run context"
            />
          </label>
          <button
            className="primary-action"
            disabled={isSubmitting || !selectedAdapter || !selectedMedia}
            type="submit"
          >
            {isSubmitting ? "Creating evidence..." : "Create proposal evidence"}
          </button>
          {!selectedMedia && !isLoading ? (
            <span className="meta-text">Import local media before running adapter contracts.</span>
          ) : null}
        </form>
      </section>

      {result ? (
        <section className="panel adapter-result-panel">
          <div className="section-heading">
            <div>
              <h2>Adapter proposals created</h2>
              <span className="meta-text">{result.local_first_note}</span>
            </div>
            <StatusPill label={`${result.review_queue_count} needs review`} tone="review" />
          </div>
          <div className="adapter-result-grid">
            <div>
              <span className="meta-text">Detection run</span>
              <strong>{result.detection_run.id}</strong>
              <span className="meta-text">{formatDateTime(result.detection_run.created_at)}</span>
            </div>
            <div>
              <span className="meta-text">Adapter truth behavior</span>
              <strong>{result.adapter.creates_review_truth ? "Writes truth" : "Evidence only"}</strong>
              <span className="meta-text">Corrected labels are dataset truth.</span>
            </div>
          </div>
          <div className="adapter-proposal-list">
            {result.proposals.map((proposal) => (
              <article className="quality-issue-card" key={proposal.id}>
                <div>
                  <div className="quality-issue-title">
                    <strong>{formatLabel(proposal.label)}</strong>
                    <ProposalStatusBadge status={proposal.status} />
                    <EvidenceBadge label="Needs review/correction" tone="review" />
                  </div>
                  <p>
                    Suggested subject: {formatLabel(proposal.suggested_subject_label)}
                    {proposal.suggested_species ? ` · Species guess: ${formatLabel(proposal.suggested_species)}` : ""}
                  </p>
                </div>
              </article>
            ))}
          </div>
          <button className="secondary-action" onClick={onOpenDetectionProposals}>
            Open Detection Proposals
          </button>
        </section>
      ) : null}
    </div>
  );
}
