import type { SpeciesSuggestion } from "../api/types";

function optionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export function speciesSuggestionMetricLabel(
  suggestion: SpeciesSuggestion,
): "uncalibrated score" | "confidence" {
  const semantics = optionalString(
    suggestion.evidence_region?.score_semantics,
  )?.toLowerCase();
  return suggestion.adapter_id === "bioclip_2" ||
    semantics?.includes("uncalibrated") ||
    semantics?.includes("candidate_relative") ||
    semantics?.includes("candidate_bank")
    ? "uncalibrated score"
    : "confidence";
}
