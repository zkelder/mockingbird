import type { TaxonomyLabel, VisitIdentificationAssistantResponse } from "../api/types";
import { displayTaxonomyLabel } from "./taxonomy";
import { explainSpeciesSuggestion } from "./suggestionExplanation";
import { formatDateTime, formatLabel } from "../utils";

interface IdentificationAssistantProps {
  assistant: VisitIdentificationAssistantResponse | null;
  error?: string | null;
  isLoading?: boolean;
  isRunning?: boolean;
  prefilledSuggestionId?: string | null;
  // Presentation only: lets a suggestion read as "Blue Jay", never the raw
  // taxonomy key. Absent, the key is humanized by formatLabel.
  taxonomyLabels?: TaxonomyLabel[];
  onAnalyze: () => void;
  onUseSuggestion: (label: string, suggestionId: string) => void;
  onRejectSuggestion?: (suggestionId: string) => void;
  onClearPrefill?: () => void;
}

export function IdentificationAssistant({
  assistant,
  error,
  isLoading = false,
  isRunning = false,
  prefilledSuggestionId,
  taxonomyLabels = [],
  onAnalyze,
  onUseSuggestion,
  onRejectSuggestion,
  onClearPrefill,
}: IdentificationAssistantProps) {
  const availability = assistant?.availability;
  const canRun = Boolean(availability?.can_run || availability?.can_run_on_best_frame);
  const selectedFrames = assistant?.selected_evidence_frames ?? [];
  const selectedFrame = selectedFrames[0];

  return (
    <section className="review-identification-assist identification-assistant" aria-label="Identification Assistant">
      <div className="section-heading">
        <div>
          <span className="eyebrow">Evidence-only review aid</span>
          <h3>Identification Assistant</h3>
          <span className="meta-text">
            Analyze only saved Visit evidence. Suggestions never save or revise a correction on their own.
          </span>
        </div>
        {/*
          The specific analyzer name (e.g. a model/architecture identifier)
          is deliberately not shown here — see suggestionExplanation.ts's
          file header. "Availability" below already reports plain-language
          readiness status.
        */}
        <strong>{availability ? "Local identification analyzer" : "Analyzer unavailable"}</strong>
      </div>

      {isLoading ? <span className="meta-text">Checking local analyzer availability...</span> : null}
      {error ? <div className="error-panel compact-error">{error}</div> : null}
      {availability ? (
        <>
          {/* Default view: one plain sentence. The model-input, candidate-pack
              and truth-boundary facts stay available on demand. */}
          <p className="meta-text">
            {availability.status === "identification_uncertain"
              ? explainSpeciesSuggestion({ isUncertain: true })
              : availability.message}
          </p>
          <details className="review-diagnostic-details">
            <summary>How suggestions work</summary>
        <div className="review-identification-grid">
          <div className="data-row">
            <span>Selected model input</span>
            <strong>{selectedFrame ? "One saved image" : "No saved image"}</strong>
            <small>High-resolution crop first, then full still, then the best monitoring evidence. No camera or live-stream access.</small>
          </div>
          {availability.candidate_pack ? (
            <div className="data-row">
              <span>Candidate pack</span>
              <strong>
                Compared against {availability.candidate_pack.candidate_count} species from {availability.candidate_pack.display_name} v{availability.candidate_pack.version}
              </strong>
              <small>
                {availability.candidate_pack_warning ?? "The selected Stream pack applies only to this explicit evidence-only request."}
              </small>
            </div>
          ) : null}
          <div className="data-row">
            <span>Truth boundary</span>
            <strong>Evidence only</strong>
            <small>Use a suggestion to prefill, then save through the existing correction workflow.</small>
          </div>
        </div>
          </details>
        </>
      ) : null}

      <div className="identification-assistant-controls">
        <button
          className="secondary-action"
          disabled={!canRun || isRunning}
          onClick={onAnalyze}
          type="button"
        >
          {isRunning ? "Suggesting species..." : "Suggest species"}
        </button>
      </div>
      {!canRun && availability ? (
        <span className="field-helper">Normal review remains available while the optional analyzer is unavailable.</span>
      ) : null}
      {prefilledSuggestionId && onClearPrefill ? (
        <div className="suggestion-prefill-summary">
          <span>A suggestion filled in the species field. Nothing is saved until you confirm.</span>
          <button className="text-action" onClick={onClearPrefill} type="button">Clear prefill</button>
        </div>
      ) : null}

      {assistant?.suggestions.length ? (
        <div className="identification-assistant-results-layout">
          {selectedFrame ? (
            <figure className="identification-assistant-input">
              <img alt="Analyzed saved evidence" src={selectedFrame.preview_url} />
              <figcaption>
                Analyzed input · {formatLabel(selectedFrame.evidence_role ?? "saved evidence")}
              </figcaption>
            </figure>
          ) : null}
          <div className="visit-suggestion-list identification-assistant-results">
          {assistant.suggestions.slice(0, 5).map((suggestion) => (
            <article className="visit-suggestion-card" key={`${suggestion.attempt_id ?? "saved"}:${suggestion.suggestion_id}:${suggestion.rank}:${suggestion.label}`}>
              <div className="item-title-row">
                <div>
                  <span className="meta-text">
                    {suggestion.origin === "previously_generated" ? "Suggested earlier" : "Suggested on request"}
                  </span>
                  <h4>{displayTaxonomyLabel(suggestion.label, taxonomyLabels)}</h4>
                </div>
                <strong>{suggestion.rank === 1 ? "Best match" : `Option ${suggestion.rank}`}</strong>
              </div>
              <p>
                {explainSpeciesSuggestion({ label: displayTaxonomyLabel(suggestion.label, taxonomyLabels) }) ??
                  `Suggested: ${displayTaxonomyLabel(suggestion.label, taxonomyLabels)}.`}
              </p>
              <span className="meta-text">{formatDateTime(suggestion.analyzed_at)}</span>
              <details className="review-diagnostic-details">
                <summary>Suggestion details</summary>
                <div className="species-suggestion-meta">
                  <span>{suggestion.provider}</span>
                  <span>{suggestion.frame_role} frame</span>
                  <span>Appeared in {suggestion.support_count} analyzed frame{suggestion.support_count === 1 ? "" : "s"}</span>
                  {suggestion.score != null ? <span>{suggestion.score_label}: {suggestion.score.toFixed(3)}</span> : null}
                </div>
                {suggestion.model_runtime_version ? <span className="meta-text">Model/runtime: {suggestion.model_runtime_version}</span> : null}
              </details>
              <div className="suggestion-action-stack">
                <button
                  className="secondary-action"
                  disabled={isRunning}
                  onClick={() => onUseSuggestion(suggestion.label, suggestion.suggestion_id)}
                  type="button"
                >
                  Use suggestion
                </button>
                <span className="field-helper">Fills in the species field only — you still confirm it.</span>
                {onRejectSuggestion && suggestion.status === "pending" ? (
                  <button
                    className="text-action"
                    disabled={isRunning}
                    onClick={() => onRejectSuggestion(suggestion.suggestion_id)}
                    type="button"
                  >
                    Dismiss suggestion
                  </button>
                ) : null}
              </div>
            </article>
          ))}
          </div>
        </div>
      ) : assistant && !isLoading ? (
        <span className="meta-text">
          {explainSpeciesSuggestion({
            isUncertain: assistant.availability?.status === "identification_uncertain",
          }) ?? "No useful suggestion is available yet. You can still review and save a correction normally."}
        </span>
      ) : null}
    </section>
  );
}
