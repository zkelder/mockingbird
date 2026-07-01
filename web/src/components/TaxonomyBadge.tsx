import type { TaxonomyLabel } from "../api/types";
import { formatLabel } from "../utils";
import { EvidenceBadge } from "./EvidenceBadge";

interface TaxonomyBadgeProps {
  label?: TaxonomyLabel | null;
  value?: string | null;
}

export function TaxonomyBadge({ label, value }: TaxonomyBadgeProps) {
  if (!label && !value) {
    return null;
  }

  const category = label?.category ?? value;
  const badgeLabel = label
    ? `${formatLabel(label.category)}${label.is_species ? " species" : ""}`
    : formatLabel(category ?? "unknown");

  return <EvidenceBadge label={badgeLabel} tone={label?.is_species ? "truth" : "quiet"} />;
}
