import type { VisitIdentificationAssistantResponse } from "../api/types";
import { formatDateTime, formatLabel } from "../utils";

interface IdentificationAssistantProps {
  assistant: VisitIdentificationAssistantResponse | null;
  error?: string | null;
  isLoading?: boolean;
  isRunning?: boolean;
  prefilledSuggestionId?: string | null;
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
        <strong>{availability?.adapter_name ?? "Analyzer unavailable"}</strong>
      </div>

      {isLoading ? <span className="meta-text">Checking local analyzer availability...</span> : null}
      {error ? <div className="error-panel compact-error">{error}</div> : null}
      {availability ? (
        <div className="review-identification-grid">
          <div className="data-row">
            <span>Availability</span>
            <strong>{formatLabel(availability.status)}</strong>
            <small>{availability.message}</small>
          </div>
          <div className="data-row">
            <span>Selected model input</span>
            <strong>{selectedFrame ? "One saved image" : "No saved image"}</strong>
            <small>High-resolution crop first, then full still, then the best monitoring evidence. No camera or live-stream access.</small>
          </div>
          <div className="data-row">
            <span>Truth boundary</span>
            <strong>Evidence only</strong>
            <small>Use a suggestion to prefill, then save through the existing correction workflow.</small>
          </div>
        </div>
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
          <span>Suggestion {prefilledSuggestionId} only prefilled the correction field.</span>
          <button className="text-action" onClick={onClearPrefill} type="button">Clear prefill</button>
        </div>
      ) : null}

      {assistant?.run ? (
        <span className="meta-text">
          Latest explicit request: {String(assistant.run.status ?? "recorded")} · {String(assistant.run.request_origin ?? "user-triggered")}
        </span>
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
                    {suggestion.origin === "previously_generated" ? "Previously generated evidence" : "User-triggered review assistance"}
                  </span>
                  <h4>Suggested label: {suggestion.label}</h4>
                </div>
                <strong>Rank {suggestion.rank}</strong>
              </div>
              <div className="species-suggestion-meta">
                <span>{suggestion.provider}</span>
                <span>{suggestion.frame_role} frame</span>
                <span>Appeared in {suggestion.support_count} analyzed frame{suggestion.support_count === 1 ? "" : "s"}</span>
                {suggestion.score != null ? <span>{suggestion.score_label}: {suggestion.score.toFixed(3)}</span> : null}
                <span>{formatDateTime(suggestion.analyzed_at)}</span>
              </div>
              {suggestion.model_runtime_version ? <span className="meta-text">Model/runtime: {suggestion.model_runtime_version}</span> : null}
              <div className="suggestion-action-stack">
                <button
                  className="secondary-action"
                  disabled={isRunning}
                  onClick={() => onUseSuggestion(suggestion.label, suggestion.suggestion_id)}
                  type="button"
                >
                  Use suggestion
                </button>
                <span className="field-helper">Prefills only. Explicit correction save remains required.</span>
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
        <span className="meta-text">No useful suggestion is available yet. You can still review and save a correction normally.</span>
      ) : null}
    </section>
  );
}
