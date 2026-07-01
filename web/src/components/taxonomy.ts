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

export function isFalsePositiveLabel(value: string | null | undefined, labels: TaxonomyLabel[]): boolean {
  const label = findTaxonomyLabel(value, labels);
  return label?.category === "false_positive" || taxonomyKey(value ?? "") === "false_positive";
}

export function isUnknownAnimalLabel(value: string | null | undefined, labels: TaxonomyLabel[]): boolean {
  const key = taxonomyKey(value ?? "");
  return key === "unknown_animal" || findTaxonomyLabel(value, labels)?.category === "unknown";
}

export function isUnknownBirdLabel(value: string | null | undefined, labels: TaxonomyLabel[]): boolean {
  return taxonomyKey(value ?? "") === "unknown_bird";
}

export function isBirdReviewLabel(value: string | null | undefined, labels: TaxonomyLabel[]): boolean {
  const key = taxonomyKey(value ?? "");
  const label = findTaxonomyLabel(value, labels);
  return key === "bird" || key === "unknown_bird" || label?.category === "bird";
}

export function birdSpeciesLabels(labels: TaxonomyLabel[]): TaxonomyLabel[] {
  return labels
    .filter((label) => label.category === "bird" && label.is_species)
    .sort((first, second) => {
      const firstOrder = first.sort_order ?? Number.MAX_SAFE_INTEGER;
      const secondOrder = second.sort_order ?? Number.MAX_SAFE_INTEGER;
      return firstOrder === secondOrder
        ? first.display_name.localeCompare(second.display_name)
        : firstOrder - secondOrder;
    });
}
