# Public Benchmark / Training Governance

This document did not exist before the 2026-08-19 roadmap/doctrine closure
pass. It closes a real, confirmed gap: MockingBird already governs frozen
evaluation holdouts and training-corpus contamination internally (see
[wildlife-detector-training-contract.md](wildlife-detector-training-contract.md)
"Leakage and frozen evaluation" and "Holdout v2 scene/session governance",
and [detector-promotion-benchmark-contract.md](detector-promotion-benchmark-contract.md)
"Corpus v1"), but nothing in the repository previously addressed what is
required before any of that material -- or any reviewed Observation corpus
more broadly -- could be legally and ethically released outside the
project. This is that layer. It does not restate the internal
frozen/contamination rules; it references them and adds what they do not
cover.

## Status

Governance only. No public benchmark or training corpus has been released
under this document. Nothing here changes training eligibility, detector/
classifier promotion authority, or reviewed truth semantics -- those remain
governed by
[review-decision-provenance-contract.md](review-decision-provenance-contract.md),
[product-doctrine.md](product-doctrine.md) ("Models earn trust; they do not
inherit it"), and the detector/wildlife-training contracts referenced above.

## The core rule

**Reviewed truth is necessary for public-release eligibility, but it does
not by itself grant public-release rights.** A `ReviewLabel` being
authority-eligible (see `mockingbird.review_provenance.is_authority_eligible`)
answers "is this dataset-grade truth" -- a separate, later question,
answered here, is "may this specific data leave the project at all, to
whom, and under what terms." Do not conflate the two. Do not let a future
public-benchmark or contribution feature quietly skip this document because
the underlying data already cleared the ordinary truth boundary.

## Requirements before any public release

All of the following must be true for a given corpus/subset before it may
be published, not merely internally reviewed:

1. **Frozen and versioned.** The exact released content is checksum-pinned
   and immutable once published; corrections ship as a new version, never a
   silent overwrite. Reuse the existing frozen-holdout pattern
   (`wildlife-detector-training-contract.md` "Leakage and frozen
   evaluation") rather than inventing a second one.
2. **Legally releasable.** Every image/clip/label has a known, sufficient
   license or consent basis for public redistribution -- this is distinct
   from, and in addition to, any model-weight or third-party-dependency
   license already tracked elsewhere (for example
   [model-selection.md](model-selection.md)'s BioCLIP 2 model-card license).
   Property/premises consent, any visible person's privacy, and Privacy/
   Ignore Zone intent all apply; do not publish evidence a user drew a
   Privacy Zone around, and do not publish identifiable people or private
   property detail without a separately confirmed release basis.
3. **Separate from training.** A frozen public benchmark is evaluation-only
   and prohibited from training use, exactly like the existing internal
   frozen holdouts -- publishing it does not relax that prohibition, it
   extends it to external users of the same corpus.
4. **Separate from ordinary private Observations.** Publication is always
   an explicit, scoped, opt-in export of a specific named corpus -- never an
   incidental consequence of a database backup, a support diagnostic
   bundle, or a generic "export everything" action. A user's ordinary
   reviewed history is never published by default or by side effect.
5. **Provenance.** Source/camera/site diversity, capture date range, and
   collection method are documented well enough that a downstream user can
   judge applicability and detect contamination against their own data.
6. **License and consent, explicit and per-item or per-batch.** State the
   exact license the release is offered under and the consent basis for
   every contributing source. Unknown or unconfirmed consent is a hard
   blocker, not a caveat to disclose and publish anyway.
7. **Taxonomic and source/camera diversity, disclosed.** State what is and
   is not represented (species, scene types, hardware) rather than implying
   general-purpose coverage a small or narrow corpus does not have.
8. **Difficulty and contamination status, disclosed.** State known
   near-duplicates, easy/hard composition, and any known relationship to
   MockingBird's own internal training/evaluation corpora (dHash/pHash
   checks, per the existing internal pattern).
9. **No quiet training on a published public holdout.** Once released, the
   project's own future model work must continue to treat that corpus as
   evaluation-only, exactly as if it were still the internal frozen
   holdout -- publication does not create a loophole to later train on it.

## What this does not cover

- Choice of an open-source license for the MockingBird codebase itself
  (see Gate F in [roadmap.md](roadmap.md); no `LICENSE` file exists yet).
- Third-party model-weight licenses (tracked per-model, e.g.
  [model-selection.md](model-selection.md)).
- Future destination-specific interoperability (eBird, Camtrap DP, GBIF,
  Wildlife Insights, iNaturalist) -- see "Post-v0.1 lanes" /
  "Ecological export & sharing interoperability" in
  [roadmap.md](roadmap.md). Those consume data already cleared under this
  document; they do not define a second release-eligibility system.
- Contributor/community dataset workflows -- gated behind Phase 8
  ("Learning / Contributor Ecosystem") in [roadmap.md](roadmap.md), which
  this document is a prerequisite for, not a replacement of.

## v0.1 relevance

This is a Gate F item, not a blocker in the sense of delaying core product
work -- see "Explicit phase gates" in [roadmap.md](roadmap.md). It matters
for v0.1 only to the extent v0.1 packaging/release work references or ships
any benchmark/example corpus publicly; it fully gates any future public
benchmark release regardless of v0.1 timing.
