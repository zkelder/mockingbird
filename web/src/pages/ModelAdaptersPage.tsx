import { useEffect, useMemo, useState, type FormEvent } from "react";
import { apiClient } from "../api/client";
import type {
  AdapterEvaluationItem,
  AdapterEvaluationSummary,
  MediaAsset,
  ModelAdapterConfigurationStatus,
  ModelAdapter,
  ModelAdapterSetupSummary,
  ModelReadinessChecklistItem,
  ModelReadinessSummary,
  ModelAdapterRunResult,
} from "../api/types";
import { EmptyState } from "../components/EmptyState";
import { EvidenceBadge } from "../components/EvidenceBadge";
import { MediaAssetPreview } from "../components/MediaAssetPreview";
import { PageHeader } from "../components/PageHeader";
import { ProposalStatusBadge } from "../components/ProposalStatusBadge";
import { StatusPill } from "../components/StatusPill";
import { formatDateTime, formatLabel } from "../utils";

const LOCAL_IMAGE_DETECTOR_ADAPTER_ID = "local_image_detector";
const LOCAL_DETECTOR_ENV_VARS = [
  {
    name: "MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH",
    description: "Required local model file path. MockingBird does not bundle or download it.",
  },
  {
    name: "MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH",
    description: "Optional newline-delimited labels file when the local detector needs one.",
  },
  {
    name: "MOCKINGBIRD_LOCAL_DETECTOR_CONFIDENCE_THRESHOLD",
    description: "Optional confidence threshold; the backend defaults safely when unset.",
  },
];

interface ModelAdaptersPageProps {
  onOpenDetectionProposals: () => void;
  onOpenEvent: (eventId: string) => void;
  onOpenExports: () => void;
  onOpenImport: () => void;
  onOpenStreams: () => void;
  onOpenReview: () => void;
  onOpenBirdLog: () => void;
  onOpenVisit: (visitId: string) => void;
  onProposalChanged: () => Promise<void>;
  modelReadiness: ModelReadinessSummary | null;
}

export function ModelAdaptersPage({
  onOpenDetectionProposals,
  onOpenEvent,
  onOpenExports,
  onOpenImport,
  onOpenStreams,
  onOpenReview,
  onOpenBirdLog,
  onOpenVisit,
  onProposalChanged,
  modelReadiness,
}: ModelAdaptersPageProps) {
  const [adapters, setAdapters] = useState<ModelAdapter[]>([]);
  const [mediaAssets, setMediaAssets] = useState<MediaAsset[]>([]);
  const [evaluation, setEvaluation] = useState<AdapterEvaluationSummary | null>(null);
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
  const selectedAdapterConfiguration = selectedAdapter?.configuration_status ?? null;
  const selectedAdapterAvailable = selectedAdapter?.status === "available";
  const selectedAdapterSupportsMedia =
    selectedAdapter && selectedMedia ? adapterSupportsMedia(selectedAdapter, selectedMedia) : false;
  const localDetectorAdapter =
    adapters.find((adapter) => adapter.id === LOCAL_IMAGE_DETECTOR_ADAPTER_ID) ?? null;

  async function loadPageData(options: { showLoading?: boolean } = {}) {
    const showLoading = options.showLoading ?? true;
    if (showLoading) {
      setIsLoading(true);
    }
    setError(null);
    try {
      const [nextAdapters, nextMediaAssets, nextEvaluation] = await Promise.all([
        apiClient.getModelAdapters(),
        apiClient.getMediaAssets(),
        apiClient.getModelAdapterEvaluation(),
      ]);
      setAdapters(nextAdapters);
      setMediaAssets(nextMediaAssets);
      setEvaluation(nextEvaluation);
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
    if (!selectedAdapterAvailable) {
      setError("Selected adapter is not available for a local evidence run.");
      return;
    }
    if (!selectedAdapterSupportsMedia) {
      setError("Selected adapter does not support this media type.");
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
        eyebrow="Advanced setup"
        title="Model Adapters"
        description="Developer-facing adapter readiness and evidence tests. Model suggestions are not review truth and are secondary to the Cameras → Review → Bird Log → Export loop."
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

      <section className="notice-panel">
        <strong>Advanced setup — not the product center</strong>
        <span>
          Adapter runs are optional evidence checks for development. Camera monitoring and review
          remain the product path.
        </span>
      </section>

      {message ? <div className="notice-panel">{message}</div> : null}
      {error ? <div className="error-panel">{error}</div> : null}

      <section className="notice-panel">
        <strong>Model adapters create evidence, not truth</strong>
        <span>
          The demo adapter simulates evidence, while local detector wrappers run only when configured
          with local model files. MegaDetector-family outputs remain animal/person/vehicle evidence;
          species truth stays in review and correction.
        </span>
      </section>

      <LocalDetectorSetupPanel
        adapter={localDetectorAdapter}
        isLoading={isLoading}
        onOpenStreams={onOpenStreams}
      />

      <RealModelSmokeCheck
        adapter={localDetectorAdapter}
        isLoading={isLoading}
        mediaCount={mediaAssets.filter((asset) => asset.media_type === "image").length}
        onOpenBirdLog={onOpenBirdLog}
        onOpenImport={onOpenImport}
        onOpenReview={onOpenReview}
        onOpenStreams={onOpenStreams}
      />

      {modelReadiness ? (
        <section className="panel model-readiness-panel">
          <div className="section-heading">
            <div>
              <h2>Pre-model readiness</h2>
              <span className="meta-text">
                {modelReadiness.local_first_note} Generated {formatDateTime(modelReadiness.generated_at)}.
              </span>
            </div>
            <StatusPill
              label={
                modelReadiness.ready_for_first_detector_spike
                  ? "Ready for first detector spike"
                  : "Readiness work remains"
              }
              tone={modelReadiness.ready_for_first_detector_spike ? "good" : "review"}
            />
          </div>
          <div className="model-readiness-grid">
            <div>
              <span className="meta-text">Reviewed local dataset</span>
              <strong>
                {modelReadiness.reviewed_record_count} reviewed · {modelReadiness.export_ready_count} export-ready
              </strong>
            </div>
            <div>
              <span className="meta-text">Dataset QA</span>
              <strong>
                {modelReadiness.dataset_quality_issue_count} issues · {modelReadiness.high_quality_issue_count} high
              </strong>
            </div>
            <div>
              <span className="meta-text">Species coverage</span>
              <strong>
                {modelReadiness.covered_target_species_count}/{modelReadiness.target_species_count} targets
              </strong>
            </div>
            <div>
              <span className="meta-text">Adapter evidence</span>
              <strong>
                {modelReadiness.adapter_reviewed_count}/{modelReadiness.adapter_proposal_count} reviewed ·{" "}
                {formatMatchRate(modelReadiness.adapter_match_rate)}
              </strong>
            </div>
          </div>
          {modelReadiness.adapter_setup.length > 0 ? (
            <div className="adapter-setup-summary-list">
              {modelReadiness.adapter_setup.map((setup) => (
                <AdapterSetupSummaryCard setup={setup} key={setup.adapter_id} />
              ))}
            </div>
          ) : null}
          <div className="notice-panel readiness-next-step">
            <strong>Safe next step</strong>
            <span>{modelReadiness.recommended_next_step}</span>
          </div>
          <div className="model-readiness-checklist">
            {modelReadiness.checklist.map((item) => (
              <ReadinessChecklistItem item={item} key={item.id} />
            ))}
          </div>
          <div className="detail-actions">
            <button className="secondary-action" onClick={onOpenReview}>
              Review Queue
            </button>
            <button className="secondary-action" onClick={onOpenExports}>
              Dataset Exports
            </button>
            <button className="secondary-action" onClick={onOpenDetectionProposals}>
              Detection Proposals
            </button>
          </div>
        </section>
      ) : null}

      {evaluation ? (
        <section className="panel adapter-evaluation-panel">
          <div className="section-heading">
            <div>
              <h2>Adapter evidence readiness</h2>
              <span className="meta-text">
                {evaluation.local_first_note} Generated {formatDateTime(evaluation.generated_at)}.
              </span>
            </div>
            <EvidenceBadge label="Readiness signal" tone="truth" />
          </div>
          <div className="adapter-evaluation-grid">
            <div>
              <span className="meta-text">Proposals</span>
              <strong>{evaluation.proposal_count}</strong>
            </div>
            <div>
              <span className="meta-text">Reviewed truth</span>
              <strong>{evaluation.reviewed_count}</strong>
            </div>
            <div>
              <span className="meta-text">Unreviewed</span>
              <strong>{evaluation.unreviewed_count}</strong>
            </div>
            <div>
              <span className="meta-text">Matched / mismatched</span>
              <strong>
                {evaluation.matched_count} / {evaluation.mismatched_count}
              </strong>
            </div>
            <div>
              <span className="meta-text">Rejected / converted</span>
              <strong>
                {evaluation.rejected_count} / {evaluation.converted_count}
              </strong>
            </div>
            <div>
              <span className="meta-text">Evidence agreement</span>
              <strong>{formatMatchRate(evaluation.match_rate)}</strong>
            </div>
          </div>
          <div className="adapter-evaluation-list">
            {evaluation.items.map((item) => (
              <EvaluationItemCard
                item={item}
                key={item.proposal_id}
                onOpenDetectionProposals={onOpenDetectionProposals}
                onOpenEvent={onOpenEvent}
                onOpenVisit={onOpenVisit}
              />
            ))}
            {evaluation.items.length === 0 ? (
              <EmptyState
                title="No adapter evidence to evaluate"
                description="Adapter proposals will appear here after they are created, converted, rejected, and corrected through the normal review loop."
              />
            ) : null}
          </div>
        </section>
      ) : null}

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
                {adapter.configuration_status ? (
                  <AdapterConfigurationStatus compact status={adapter.configuration_status} />
                ) : adapter.notes ? (
                  <span>{adapter.notes}</span>
                ) : null}
                <div className="adapter-badge-row">
                  <StatusPill
                    label={formatLabel(adapter.status)}
                    tone={adapter.status === "available" ? "good" : "review"}
                  />
                  <EvidenceBadge
                    label={adapter.creates_review_truth ? "Writes truth" : "Evidence only"}
                    tone={adapter.creates_review_truth ? "review" : "truth"}
                  />
                  {adapter.local_only ? <EvidenceBadge label="Local-only adapter" tone="quiet" /> : null}
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
          {selectedAdapterConfiguration ? (
            <AdapterConfigurationStatus status={selectedAdapterConfiguration} />
          ) : selectedAdapter?.notes ? (
            <span className="field-helper">{selectedAdapter.notes}</span>
          ) : null}
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
            disabled={
              isSubmitting ||
              !selectedAdapter ||
              !selectedMedia ||
              !selectedAdapterAvailable ||
              !selectedAdapterSupportsMedia
            }
            type="submit"
          >
            {isSubmitting ? "Creating evidence..." : "Create proposal evidence"}
          </button>
          {selectedAdapter && !selectedAdapterAvailable ? (
            <span className="meta-text">
              Configure the adapter locally before running it. Evidence remains separate from truth.
            </span>
          ) : null}
          {selectedAdapter && selectedMedia && !selectedAdapterSupportsMedia ? (
            <span className="meta-text">Choose supported imported media for this adapter.</span>
          ) : null}
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

function LocalDetectorSetupPanel({
  adapter,
  isLoading,
  onOpenStreams,
}: {
  adapter: ModelAdapter | null;
  isLoading: boolean;
  onOpenStreams: () => void;
}) {
  const configuration = adapter?.configuration_status ?? null;
  const statusLabel = isLoading
    ? "Loading"
    : adapter
      ? formatLabel(adapter.status)
      : "Unavailable";
  const supportedMediaTypes =
    configuration?.supported_media_types ?? adapter?.supported_media_types ?? [];

  return (
    <section className="panel local-detector-setup-panel">
      <div className="section-heading">
        <div>
          <h2>Local Detector setup</h2>
          <span className="meta-text">
            Configure local files yourself, then run the detector explicitly from saved media.
          </span>
        </div>
        <StatusPill label={statusLabel} tone={adapterStatusTone(adapter?.status)} />
      </div>

      {!adapter && !isLoading ? (
        <div className="error-panel">
          <strong>Local detector adapter status is unavailable.</strong>
          <span>
            The app remains usable. Demo proposal evidence is still available for smoke testing.
          </span>
        </div>
      ) : null}

      <div className="local-detector-setup-grid">
        <SetupStatusRow
          label="Adapter"
          value={adapter ? `${adapter.name} (${adapter.id})` : LOCAL_IMAGE_DETECTOR_ADAPTER_ID}
          ready={Boolean(adapter)}
        />
        <SetupStatusRow
          label="Model path"
          value={yesNo(configuration?.model_path_configured ?? false)}
          ready={Boolean(configuration?.model_path_configured)}
        />
        <SetupStatusRow
          label="Labels path"
          value={yesNo(configuration?.labels_path_configured ?? false)}
          ready={Boolean(configuration?.labels_path_configured)}
          optional
        />
        <SetupStatusRow
          label="Runtime"
          value={yesNo(configuration?.runtime_available ?? false)}
          ready={Boolean(configuration?.runtime_available)}
        />
        <SetupStatusRow
          label="Can run"
          value={yesNo(configuration?.can_run ?? false)}
          ready={Boolean(configuration?.can_run)}
        />
        <SetupStatusRow
          label="Local only"
          value={yesNo(configuration?.local_only ?? adapter?.local_only ?? true)}
          ready={configuration?.local_only ?? adapter?.local_only ?? true}
        />
        <SetupStatusRow
          label="Creates truth"
          value={yesNo(configuration?.creates_review_truth ?? adapter?.creates_review_truth ?? false)}
          ready={!(configuration?.creates_review_truth ?? adapter?.creates_review_truth ?? false)}
          inverted
        />
        <SetupStatusRow
          label="Supported media"
          value={supportedMediaTypes.length > 0 ? supportedMediaTypes.join(", ") : "Unknown"}
          ready={supportedMediaTypes.length > 0}
        />
      </div>

      <div className="local-detector-setup-copy">
        <div>
          <strong>Status reason</strong>
          <span>{configuration?.status_reason ?? adapter?.notes ?? "Adapter status is loading."}</span>
        </div>
        <div>
          <strong>Setup hint</strong>
          <span>
            {configuration?.setup_hint ??
              "Set a local model path before running this optional detector."}
          </span>
        </div>
      </div>

      <div className="local-detector-env-list" aria-label="Local detector environment variables">
        {LOCAL_DETECTOR_ENV_VARS.map((item) => (
          <div className="local-detector-env-row" key={item.name}>
            <code>{item.name}</code>
            <span>{item.description}</span>
          </div>
        ))}
      </div>

      <div className="notice-panel local-detector-boundary">
        <strong>Local-first detector boundary</strong>
        <span>
          Model files are not bundled. MockingBird does not download models. Configure a
          local model path yourself. Outputs become DetectionProposal evidence only;
          ReviewLabel correction remains truth. Demo proposal remains available for smoke
          testing when the detector is not configured.
        </span>
      </div>

      <div className="detail-actions">
        <button className="primary-action" onClick={onOpenStreams} type="button">
          Open Streams
        </button>
        <span className="meta-text">
          Use the saved media timeline to run the detector explicitly on image media.
        </span>
      </div>
    </section>
  );
}

function RealModelSmokeCheck({
  adapter,
  isLoading,
  mediaCount,
  onOpenBirdLog,
  onOpenImport,
  onOpenReview,
  onOpenStreams,
}: {
  adapter: ModelAdapter | null;
  isLoading: boolean;
  mediaCount: number;
  onOpenBirdLog: () => void;
  onOpenImport: () => void;
  onOpenReview: () => void;
  onOpenStreams: () => void;
}) {
  const configuration = adapter?.configuration_status ?? null;
  const modelReady = Boolean(configuration?.can_run);
  const hasSavedImages = mediaCount > 0;

  return (
    <section className="panel real-model-smoke-panel">
      <div className="section-heading">
        <div>
          <h2>Real model smoke check</h2>
          <span className="meta-text">
            Prove a configured local model can suggest labels from saved images without creating reviewed data.
          </span>
        </div>
        <StatusPill
          label={modelReady && hasSavedImages ? "Ready to try" : "Needs setup"}
          tone={modelReady && hasSavedImages ? "good" : "review"}
        />
      </div>

      <div className="real-model-smoke-grid">
        <SmokeCheckRow
          label="Local model"
          ready={modelReady}
          value={
            isLoading
              ? "Loading"
              : modelReady
                ? "Configured and runnable"
                : "Not configured"
          }
        />
        <SmokeCheckRow
          label="Saved images"
          ready={hasSavedImages}
          value={hasSavedImages ? `${mediaCount} image${mediaCount === 1 ? "" : "s"}` : "None yet"}
        />
        <SmokeCheckRow
          label="Run action"
          ready={modelReady && hasSavedImages}
          value="Cameras/Streams saved image"
        />
        <SmokeCheckRow
          label="Truth boundary"
          ready
          value="Correction creates reviewed data"
        />
      </div>

      <div className="real-model-smoke-steps">
        <strong>How to smoke test</strong>
        <ol>
          <li>Set local model env vars if you have a model file.</li>
          <li>Restart the API so readiness updates.</li>
          <li>Capture or import an image.</li>
          <li>Open Cameras/Streams and click Analyze image on a saved image.</li>
          <li>Confirm a Suggested label appears, then Review suggestion.</li>
          <li>Correct label, confirm the item in Bird Log, then Export reviewed data.</li>
        </ol>
      </div>

      <div className="detail-actions">
        <button className="secondary-action" onClick={onOpenStreams} type="button">
          Cameras / Streams
        </button>
        <button className="secondary-action" onClick={onOpenImport} type="button">
          Import image
        </button>
        <button className="secondary-action" onClick={onOpenReview} type="button">
          Review
        </button>
        <button className="secondary-action" onClick={onOpenBirdLog} type="button">
          Bird Log
        </button>
      </div>
    </section>
  );
}

function SmokeCheckRow({
  label,
  ready,
  value,
}: {
  label: string;
  ready: boolean;
  value: string;
}) {
  return (
    <div className="real-model-smoke-row">
      <span>{label}</span>
      <strong>{value}</strong>
      <EvidenceBadge label={ready ? "Ready" : "Needs setup"} tone={ready ? "truth" : "review"} />
    </div>
  );
}

function SetupStatusRow({
  inverted = false,
  label,
  optional = false,
  ready,
  value,
}: {
  inverted?: boolean;
  label: string;
  optional?: boolean;
  ready: boolean;
  value: string;
}) {
  return (
    <div className="local-detector-setup-row">
      <span>{label}</span>
      <strong>{value}</strong>
      <EvidenceBadge
        label={optional ? "Optional" : ready ? (inverted ? "Safe" : "Ready") : "Needs setup"}
        tone={optional || ready ? "truth" : "review"}
      />
    </div>
  );
}

function ReadinessChecklistItem({ item }: { item: ModelReadinessChecklistItem }) {
  return (
    <article className="readiness-checklist-item">
      <div className="quality-issue-title">
        <strong>{item.label}</strong>
        <EvidenceBadge label={formatLabel(item.status)} tone={readinessTone(item)} />
        <StatusPill label={formatLabel(item.severity)} tone={item.severity === "high" ? "review" : "quiet"} />
      </div>
      <p>{item.description}</p>
      <span className="meta-text">{item.suggested_action}</span>
    </article>
  );
}

function AdapterSetupSummaryCard({ setup }: { setup: ModelAdapterSetupSummary }) {
  const statusTone = setup.status === "available" || setup.status === "demo" ? "truth" : "review";
  return (
    <article className="adapter-setup-summary-card">
      <div className="quality-issue-title">
        <strong>{setup.adapter_name}</strong>
        <EvidenceBadge label={formatLabel(setup.status)} tone={statusTone} />
        {setup.is_demo ? <StatusPill label="Demo" tone="quiet" /> : null}
      </div>
      <div className="adapter-setup-summary-grid">
        <div>
          <span>Adapter</span>
          <strong>{setup.adapter_id}</strong>
          <small>{formatLabel(setup.adapter_kind)}</small>
        </div>
        <div>
          <span>Required env</span>
          <strong>{setup.required_env_var ?? "None"}</strong>
          <small>{setup.model_path_hint ?? "No local model file required."}</small>
        </div>
        <div>
          <span>Supported media</span>
          <strong>{setup.supported_media_types.join(", ")}</strong>
          <small>{setup.can_run_on_review_best_frame ? "Ready for review best frames" : "Setup needed before runs"}</small>
        </div>
        <div>
          <span>Truth boundary</span>
          <strong>{setup.creates_truth ? "Creates truth" : "Evidence only"}</strong>
          <small>No model files are bundled or downloaded.</small>
        </div>
      </div>
      {setup.setup_hint ? <span className="meta-text">{setup.setup_hint}</span> : null}
    </article>
  );
}

function EvaluationItemCard({
  item,
  onOpenDetectionProposals,
  onOpenEvent,
  onOpenVisit,
}: {
  item: AdapterEvaluationItem;
  onOpenDetectionProposals: () => void;
  onOpenEvent: (eventId: string) => void;
  onOpenVisit: (visitId: string) => void;
}) {
  return (
    <article className="quality-issue-card adapter-evaluation-item">
      <div>
        <div className="quality-issue-title">
          <strong>{item.proposal_display_name ?? formatLabel(item.proposal_label)}</strong>
          <EvidenceBadge label={formatLabel(item.outcome)} tone={evaluationTone(item)} />
          <StatusPill label={formatLabel(item.review_status)} tone={item.review_status === "reviewed" ? "good" : "review"} />
        </div>
        <p>
          Proposal: {item.proposal_display_name ?? formatLabel(item.proposal_label)} · Reviewed:{" "}
          {item.reviewed_display_name ?? (item.reviewed_label ? formatLabel(item.reviewed_label) : "Not reviewed")} ·
          Confidence: {Math.round(item.proposal_confidence * 100)}%
        </p>
        {item.notes ? <span className="meta-text">{item.notes}</span> : null}
      </div>
      <div className="detail-actions">
        {item.event_id ? (
          <button className="secondary-action" onClick={() => onOpenEvent(item.event_id!)}>
            Event detail
          </button>
        ) : null}
        {item.visit_id ? (
          <button className="secondary-action" onClick={() => onOpenVisit(item.visit_id!)}>
            Visit detail
          </button>
        ) : null}
        <button className="secondary-action" onClick={onOpenDetectionProposals}>
          Detection Proposals
        </button>
      </div>
    </article>
  );
}

function formatMatchRate(rate?: number | null): string {
  if (rate === null || rate === undefined) {
    return "Needs reviewed labels";
  }
  return `${Math.round(rate * 100)}%`;
}

function AdapterConfigurationStatus({
  compact = false,
  status,
}: {
  compact?: boolean;
  status: ModelAdapterConfigurationStatus;
}) {
  return (
    <div className={`adapter-config-status${compact ? " compact" : ""}`}>
      <div className="adapter-config-grid">
        <div>
          <span>Model path</span>
          <strong>{yesNo(status.model_path_configured)}</strong>
        </div>
        <div>
          <span>Labels</span>
          <strong>{yesNo(status.labels_path_configured)}</strong>
        </div>
        <div>
          <span>Runtime</span>
          <strong>{yesNo(status.runtime_available)}</strong>
        </div>
        <div>
          <span>Safe to run</span>
          <strong>{yesNo(status.can_run)}</strong>
        </div>
      </div>
      <span className="meta-text">{status.status_reason}</span>
      {!compact ? (
        <>
          <span className="field-helper">Supported media: {status.supported_media_types.join(", ")}</span>
          <span className="field-helper">{status.setup_hint}</span>
        </>
      ) : null}
    </div>
  );
}

function adapterSupportsMedia(adapter: ModelAdapter, media: MediaAsset): boolean {
  return (
    adapter.supported_media_types.includes(media.media_type) ||
    adapter.supported_media_types.includes(media.content_type)
  );
}

function yesNo(value: boolean): string {
  return value ? "Yes" : "No";
}

function adapterStatusTone(status?: ModelAdapter["status"]): "good" | "review" | "quiet" {
  if (status === "available") {
    return "good";
  }
  if (status === "not_configured" || status === "unavailable") {
    return "review";
  }
  return "quiet";
}

function evaluationTone(item: AdapterEvaluationItem): "quiet" | "review" | "truth" {
  if (item.outcome === "matched_reviewed_truth") {
    return "truth";
  }
  if (item.outcome === "rejected_evidence" || item.outcome === "awaiting_review") {
    return "quiet";
  }
  return "review";
}

function readinessTone(item: ModelReadinessChecklistItem): "quiet" | "review" | "truth" {
  if (item.status === "ready") {
    return "truth";
  }
  if (item.severity === "high") {
    return "review";
  }
  return "quiet";
}
