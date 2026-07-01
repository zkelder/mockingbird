import type { TaxonomyLabel } from "../api/types";
import { formatLabel } from "../utils";

export function taxonomyKey(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/-/g, "_")
    .replace(/\s+/g, "_")
    .replace(/[^a-z0-9_]+/g, "")
    .replace(/_+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export function findTaxonomyLabel(
  value: string | null | undefined,
  labels: TaxonomyLabel[],
): TaxonomyLabel | null {
  if (!value) {
    return null;
  }
  const key = taxonomyKey(value);
  return (
    labels.find((label) => {
      const candidates = [label.id, label.label, label.display_name, ...label.aliases];
      return candidates.some((candidate) => taxonomyKey(candidate) === key);
    }) ?? null
  );
}

export function displayTaxonomyLabel(
  value: string | null | undefined,
  labels: TaxonomyLabel[],
): string {
  return findTaxonomyLabel(value, labels)?.display_name ?? formatLabel(value ?? "unknown");
}
