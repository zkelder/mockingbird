# Contribution / Sharing Model Contract

**Status:** Appliance / Storage / Privacy / Recovery v1, Phase K. This is a
consistency/privacy-closure document, not new service development. Bounded
archaeology confirmed no cloud contribution backend exists anywhere in this
codebase today (comprehensive grep for HTTP-upload/cloud-sync patterns found
none; the research/export docs already state "strictly local-first: no
cloud sync, no remote researcher accounts, no distributed dataset
synchronization"). This document establishes the doctrine a future
contribution feature must satisfy *before* it is built, and records that
nothing in the product today violates it -- trivially true while nothing
exists, but the boundary is worth writing down before something does.

## The three levels

1. **Local Only** -- the default, and the only level implemented today.
   Every core product capability (monitoring, Today, Bird Log, review/
   correction, local species identification, backup/restore, export)
   works fully with nothing ever leaving the device. See
   [research-conservation-export-contract.md](research-conservation-export-contract.md)
   and Journey 12 in this milestone's acceptance record.
2. **Derived Data Contribution** -- optional, not implemented. Would allow
   sharing *non-reconstructable* facts (a reviewed species label, a coarse
   date, a coarse site-level location) for aggregate/research purposes,
   never media or anything that could reconstruct media.
3. **Media Contribution** -- optional, purpose-specific, explicit consent,
   not implemented. Would allow sharing actual media (an image/clip) only
   when a user explicitly and separately opts in for a stated purpose.

Levels 2 and 3 are named here as the doctrine's own boundary for *whenever*
either is eventually built -- not a roadmap commitment for this milestone
or a promise either will exist soon. See "Known bounded gaps" in
[roadmap.md](roadmap.md) Phase 8 ("Learning / Contributor Ecosystem") for
where that future work is actually sequenced.

## What Derived Data Contribution must never include

If Level 2 is ever built, its payload must never contain:

- image/video/audio bytes;
- thumbnails or crops (pixel data in any form);
- raw frames;
- embeddings or any reconstructable media-derived feature vector;
- precise home/property coordinates (a coarse, user-controlled site-level
  approximation only, if location is included at all);
- local file paths;
- unrestricted free-text notes;
- faces, people, or vehicle imagery or identifiers.

## Closest existing analog, and what it is not

The generic research export (CSV/JSON/Camtrap DP; see
[research-conservation-export-contract.md](research-conservation-export-contract.md))
is the closest existing shape to what a future Level 2 payload might reuse
-- it is already metadata-only by construction (no media bytes copied by
default; `include_media` is an accepted-but-explicitly-no-op flag), never
includes local file paths or credentials (test-enforced), and never
fabricates or infers GPS coordinates (only an optional, explicit, coarse,
per-export override). It is **not** a contribution feature today: every
export is a local file written to local disk via an explicit CLI/API call,
never transmitted anywhere by this product.

Two fields in that existing export/collection shape are flagged, not fixed,
here: `ResearchObservation.reviewed_by` (free-text reviewer identity) and
`ResearchCollectionModel.curator_identity` (free-text curator identity) are
uncontrolled strings a user could type anything into. Nothing in the
product consumes them externally today, so this is not a live exposure --
but whoever designs a real Level 2 payload must not reuse this shape
uncritically; these fields would need an explicit filter/redaction pass
first, per "unrestricted free-text notes" above.

## Verification performed this milestone

- Repository-wide search for any HTTP client/cloud-sync code path outside
  this codebase's own internal ASGI test client: none found.
- Confirmed every export mechanism (generic research export, Camtrap DP,
  conservation report, classifier-training dataset export) writes only to
  local disk via an explicit, user-triggered action -- no scheduled,
  automatic, or background caller of any of them exists.
- Confirmed masking/privacy-zone enforcement (see
  [privacy-ignore-zone-contract.md](privacy-ignore-zone-contract.md)) has no
  path by which excluded content reaches any export or contribution-adjacent
  surface, since it never becomes ordinary evidence in the first place.
- Confirmed Local Only operation is not a "mode" toggle but simply the
  product's only real operating condition today -- there is no alternative
  to fall back from.

## Non-goals

- Building a cloud contribution backend (none exists; this document does
  not create one).
- A UI for Level 2/3 (neither is implemented).
- Facial/person/vehicle analytics of any kind.
- Framing this document as security/surveillance administration -- it is a
  plain statement of what local-first ownership means and what a future
  sharing feature would owe the user before it could ever be built.
