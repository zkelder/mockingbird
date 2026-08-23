# Suggestion Explanation v1

Everyday Discovery / Product Experience v2 (Phase J). Where a user reasonably
asks "Why does MockingBird think this is a Northern Cardinal?", the product
must answer in ordinary language from facts it actually has -- never logits,
embeddings, classifier internals, raw model architecture names, adapter/
provider identifiers, or model/runtime version strings.

## The shared composer

`web/src/components/suggestionExplanation.ts` is the one place these
sentences are composed:

- `explainSpeciesSuggestion({ label, isUncertain })` -- "The bird's
  appearance matched X." when a label is available, or "The image was too
  unclear for a reliable species suggestion." when the analyzer reported a
  genuine abstention (`identification_uncertain` -- an eligibility/ranking
  abstention already computed server-side, never a raw score compared
  against an invented threshold). Returns `null` (never a guess) when
  neither fact is available; every caller keeps its own calm generic
  fallback for that case.
- `explainMultimodalAssociation({ currentLabel, otherLabel, otherModality,
  tier, taxonAgreement })` -- "The visual and sound evidence agree." /
  "The sound suggested X, but the image suggested Y." / "A X was also heard
  at the same time." Returns `null` for a merely-`"possible"` tier (only a
  confidently-`"associated"` pair is asserted as a real encounter
  comparison, matching
  [multimodal-list-presentation-contract.md](multimodal-list-presentation-contract.md))
  or when a required label is missing. Only ever called from a surface that
  genuinely has both a visual and an acoustic suggestion to compare --
  `VisitDetailPage.tsx`'s existing multimodal association panel is the one
  place that does today; a single-image surface like
  `IdentificationAssistant.tsx` never fabricates this angle.

Both functions are pure and read no state of their own -- callers supply
already-resolved display strings (species names, etc.); the composer never
looks up or formats a taxonomy label itself.

## Where advanced provenance still lives

`IdentificationAssistant.tsx` and `ReviewQueuePage.tsx`'s review card now
lead with the plain sentence; the raw `provider`/`frame_role`/
`support_count`/`score`/`model_runtime_version` fields moved into a
closed-by-default `<details class="review-diagnostic-details">` disclosure
below it (the same disclosure pattern `ReviewQueuePage.tsx` already used
elsewhere for secondary/advanced detail -- no new UI pattern introduced).
`SpeciesSuggestionsPage.tsx` is a manual suggestion-authoring/debug tool
(not an ordinary end-user surface); it keeps its Adapter/confidence detail
visible but now also leads with the plain sentence first.

## Non-goals

This is presentation only: no new backend field, no new confidence
threshold, no new abstention logic. Every fact used already existed
(`identification_uncertain` status, `taxon_agreement`, association `tier`,
already-resolved labels); this only changes how they are *worded*.
