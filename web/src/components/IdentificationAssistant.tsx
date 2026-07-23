import { useState } from "react";
import type {
  VisitIdentificationAssistantResponse,
  VisitIdentificationEvidenceMode,
} from "../api/types";
import { formatDateTime, formatLabel } from "../utils";

interface IdentificationAssistantProps {
  assistant: VisitIdentificationAssistantResponse | null;
  error?: string | null;
  isLoading?: boolean;
  isRunning?: boolean;
  prefilledSuggestionId?: string | null;
  onAnalyze: (mode: VisitIdentificationEvidenceMode) => void;
  onUseSuggestion: (label: string, suggestionId: string) => void;
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
  onClearPrefill,
}: IdentificationAssistantProps) {
  const [evidenceMode, setEvidenceMode] = useState<VisitIdentificationEvidenceMode>(
    "all_retained_evidence",
  );
  const availability = assistant?.availability;
  const canRun = Boolean(availability?.can_run || availability?.can_run_on_best_frame);
  const selectedFrames = assistant?.selected_evidence_frames ?? [];

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
            <span>Saved evidence</span>
            <strong>{selectedFrames.length} retained frame{selectedFrames.length === 1 ? "" : "s"}</strong>
            <small>Primary plus at most three supporting frames; no camera or live-stream access.</small>
          </div>
          <div className="data-row">
            <span>Truth boundary</span>
            <strong>Evidence only</strong>
            <small>Use a suggestion to prefill, then save through the existing correction workflow.</small>
          </div>
        </div>
      ) : null}

      <div className="identification-assistant-controls">
        <label>
          <input
            checked={evidenceMode === "primary_only"}
            disabled={isRunning}
            name="identification-evidence-mode"
            onChange={() => setEvidenceMode("primary_only")}
            type="radio"
          />
          Primary frame only
        </label>
        <label>
          <input
            checked={evidenceMode === "all_retained_evidence"}
            disabled={isRunning}
            name="identification-evidence-mode"
            onChange={() => setEvidenceMode("all_retained_evidence")}
            type="radio"
          />
          All retained evidence
        </label>
        <button
          className="secondary-action"
          disabled={!canRun || isRunning}
          onClick={() => onAnalyze(evidenceMode)}
          type="button"
        >
          {isRunning ? "Analyzing saved evidence..." : "Analyze evidence"}
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
        <div className="visit-suggestion-list identification-assistant-results">
          {assistant.suggestions.map((suggestion) => (
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
              </div>
            </article>
          ))}
        </div>
      ) : assistant && !isLoading ? (
        <span className="meta-text">No useful suggestion is available yet. You can still review and save a correction normally.</span>
      ) : null}
    </section>
  );
}
