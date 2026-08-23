import type { EvidenceModality, MultimodalTier, TaxonAgreement } from "../api/types";

// Everyday Discovery / Product Experience v2, Phase J (see docs/multimodal-
// list-presentation-contract.md's "Ordinary-language wording (Phase J
// overlap)" section). Where a user reasonably asks "Why does MockingBird
// think this is a Northern Cardinal?", these helpers compose an ordinary-
// language explanation sentence from fields a caller already has -- never
// logits, embeddings, classifier internals, raw model architecture names,
// adapter/provider identifiers, or model/runtime version strings.
//
// Deliberately conservative: every function here returns `null` rather than
// guessing when a required fact is not reliably present, so a caller always
// has a safe, generic fallback to fall back on instead of a fabricated
// rationalization. Callers own their own already-resolved display strings
// (species display name, taxonomy formatting, etc.) -- these helpers only
// ever compose sentences, they never format or look up species names
// themselves.

function optionalString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

export interface SpeciesSuggestionExplanationInput {
  /** Already-resolved display label for the suggested species (e.g. a common name). */
  label?: string | null;
  /**
   * True when the analyzer itself reported a genuine abstention -- e.g.
   * `ReviewIdentificationStatus.identification_uncertain` (Identification
   * Eligibility + Abstention v1): evidence did not meet the identification
   * eligibility floor, or the ranked candidates were too ambiguous to name
   * a species. This is the one reliable "unclear" signal available anywhere
   * in this codebase today -- deliberately NOT a raw score compared against
   * an invented numeric cutoff, since an uncalibrated candidate-relative
   * score is not meaningfully comparable to a fixed threshold at all.
   */
  isUncertain?: boolean;
}

/**
 * Composes the plain-language sentence explaining a single species
 * suggestion, or its genuine absence. Returns `null` when neither a label
 * nor a known uncertainty signal is available -- callers should fall back
 * to their own calmer, generic copy in that case rather than treat `null`
 * as an error.
 */
export function explainSpeciesSuggestion(
  input: SpeciesSuggestionExplanationInput,
): string | null {
  const label = optionalString(input.label);
  if (label) {
    return `The bird's appearance matched ${label}.`;
  }
  if (input.isUncertain) {
    return "The image was too unclear for a reliable species suggestion.";
  }
  return null;
}

export interface MultimodalAssociationExplanationInput {
  /** Already-resolved display label for this Visit's own species (visual or acoustic, whichever this Visit is). */
  currentLabel?: string | null;
  /** Already-resolved display label for the associated opposite-modality Visit's species. */
  otherLabel?: string | null;
  /**
   * The *other* Visit's modality. This Visit's own modality is always the
   * opposite -- see `VisitMultimodalAssociation`'s own doc comment in
   * api/types.ts ("a durable link between this Visit and one opposite-
   * modality Visit (visual <-> acoustic)").
   */
  otherModality: EvidenceModality;
  /** "associated" | "possible" -- see AssociationTier's own defined confidence semantics. */
  tier: MultimodalTier;
  /** "agrees" | "differs" | "not_comparable" */
  taxonAgreement: TaxonAgreement;
}

/**
 * Composes the plain-language sentence comparing a visual and an acoustic
 * suggestion for the same real-world encounter, echoing the wording
 * VisitDetailPage.tsx's own multimodal association panel already
 * established ("Also heard nearby" / "Evidence agrees" / "Evidence
 * differs"). Only ever call this where both a visual and an acoustic
 * suggestion genuinely exist to compare -- never fabricate this angle for a
 * component (e.g. IdentificationAssistant) that only ever sees one still
 * image with no acoustic-pairing context.
 *
 * Returns `null` for a merely-"possible" association (matching docs/
 * multimodal-list-presentation-contract.md rule 1: only a confidently-
 * "associated" pair is asserted as a real encounter comparison) or when the
 * other Visit's label is not available.
 */
export function explainMultimodalAssociation(
  input: MultimodalAssociationExplanationInput,
): string | null {
  if (input.tier !== "associated") {
    return null;
  }
  const otherLabel = optionalString(input.otherLabel);
  if (!otherLabel) {
    return null;
  }

  if (input.taxonAgreement === "agrees") {
    return "The visual and sound evidence agree.";
  }

  if (input.taxonAgreement === "differs") {
    const currentLabel = optionalString(input.currentLabel);
    if (!currentLabel) {
      return null;
    }
    const acousticLabel = input.otherModality === "acoustic" ? otherLabel : currentLabel;
    const visualLabel = input.otherModality === "acoustic" ? currentLabel : otherLabel;
    return `The sound suggested ${acousticLabel}, but the image suggested ${visualLabel}.`;
  }

  // "not_comparable": still worth naming the other modality's evidence
  // without asserting an agreement judgement we can't actually support.
  return input.otherModality === "acoustic"
    ? `A ${otherLabel} was also heard at the same time.`
    : `A ${otherLabel} was also seen nearby.`;
}
