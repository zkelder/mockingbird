# Media-Copy Export Design

## Purpose

Metadata exports already reference reviewed media-backed examples. Some external
training workflows may eventually need a copied local media bundle so experiments
can run outside the core app without depending on live MockingBird media paths.

This design defines the boundary before any actual media copying,
dataset-generation, training, dependency, or runtime work is implemented.
Phase 9X implements dry-run media planning only.
Phase 9Y adds the external workspace checklist for reviewing dry-run output
before any actual media-copy implementation.
Phase 9Z documents the external workspace template that future copy-media output
should fit.

## Product Flow

reviewed media-backed Visit -> classifier manifest metadata export -> optional
future media-copy export -> external training workspace -> external
train/evaluate workflow -> future trained classifier adapter ->
`SpeciesSuggestion` evidence -> user correction remains truth.

## Media-Copy Boundary

- Media copying is optional future functionality.
- Metadata-only export already exists and remains valid on its own.
- Phase 9X `copy_media` support is dry-run only.
- Copy-media dry-run output should be reviewed with
  [external-training-workspace-checklist.md](external-training-workspace-checklist.md)
  before actual copying.
- Future copy-media output should fit
  [external-training-workspace-template.md](external-training-workspace-template.md).
- Copied media is for external training workspace convenience.
- Copied media does not create truth.
- Copied media does not train a model by itself.
- Copied media must stay local and under ignored export/data paths.
- No cloud upload happens by default.

## Source Media Policy

Future media-copy export may copy:

- `MediaAsset` records referenced by classifier manifest examples.
- Representative media associated with reviewed Visits.
- `snapshot_media_asset_id` only when it maps to reviewed training examples.
- Only examples backed by reviewed correction truth.

It must not copy:

- unreviewed media
- media from privacy zones
- media from ignore zones unless a later explicit policy allows it
- missing or stale media references
- unsupported media types
- media tied only to `SpeciesSuggestion`, `MotionEvidence`, or
  `DetectionProposal` without reviewed correction truth

## Output Layout Policy

Future exports should live under an ignored local data/export path and may
contain:

- `media/`
- `manifest.jsonl`
- `taxonomy.json`
- `skipped_records.jsonl`
- `summary.json`
- `labels.txt`
- optional by-label folders in a later phase

Recommended initial layout:

- `media/<example_id>.<ext>`
- `manifest.jsonl` references `copied_media_path`
- no class-folder layout at first, to avoid label leakage and split confusion

## File Naming Policy

- Use safe file names only.
- Use stable `example_id`-based names.
- Preserve the original extension when it is safe and supported.
- Avoid original file names when they may reveal private context.
- Prevent path traversal and absolute-path writes.
- Avoid collisions deterministically.
- Record the original `MediaAsset` ID in the manifest.

## Privacy And Ignore Policy

- Privacy zones suppress media copy.
- Ignore zones suppress media copy by default.
- No cloud upload happens by default.
- Users should understand where copied files are stored before copy starts.
- Future UI should make the copy action explicit.
- Export cleanup/reset behavior must be documented before implementation.

## Media Type Policy

Initial supported media should be still images first if the existing
`MediaAsset` type allows a simple local reference.

Video copying can be deferred. Derived crops, thumbnails, and other generated
media are future work. Unsupported media should be skipped with a specific
reason.

This phase does not implement decoding, cropping, thumbnailing, or media IO.

## Manifest Relationship

Media-copy export should be driven by the existing classifier manifest
preview/export data.

- A future `copied_media_path` may be added to manifest examples.
- `skipped_records.jsonl` should include media-copy-specific failures.
- Taxonomy, split, provenance, quality flags, and reviewed-truth policy must
  remain consistent with the metadata manifest.
- Reference-only metadata export remains the baseline behavior.

## Skip Reason Additions

Future media-copy implementation may add these skip reasons:

- `media_copy_disabled`
- `media_source_missing`
- `media_path_outside_allowed_root`
- `unsupported_media_type`
- `privacy_zone_media`
- `ignore_zone_media`
- `copy_failed`
- `duplicate_media_policy_excluded`
- `storage_limit_exceeded`

## Storage And Cleanup Policy

- Copied media can be large.
- Exports must live under ignored local export paths.
- Future implementation should report size estimates when possible.
- Cleanup/reset behavior must be explicit.
- Repeated exports should create separate directories.
- Copied media must not be committed.

## API Design

Phase 9X extends:

`POST /api/classifier-training-manifest/exports`

Request policy:

- `media_policy: "reference_only"` works for dry-run and non-dry-run exports.
- `media_policy: "copy_media"` works only when `dry_run` is `true`.
- `media_policy: "copy_media"` with `dry_run` false is rejected.
- `max_media_bytes` and `include_video` remain future options.

Phase 9X response fields:

- `media_policy`
- `planned_media_files`
- `skipped_media`
- `total_planned_media_bytes`

Actual copied-media file fields remain future work.

## Dry-Run Behavior

Phase 9X dry-run behavior:

- estimate what media would be copied
- write no files
- report skipped media reasons
- help users avoid unexpected storage use
- never create copied media directories
- never copy or decode media

## Truth Boundary

- Copying media does not create `ReviewLabel`.
- Copying media does not mark Visit reviewed.
- Copying media does not create dataset coverage truth.
- Copying media does not create `SpeciesSuggestion`.
- Copied media is training artifact/context only.
- Dry-run media planning is report metadata only.
- Training output must return `SpeciesSuggestion` evidence only.

## External Training Relationship

The copied media bundle is input to an external workspace.

- Training dependencies remain outside the core app.
- Model checkpoints remain outside the core app or under ignored local model
  paths.
- No production accuracy claims should be made without evaluation.

## Test Plan For Future Implementation

Future tests should prove:

- `reference_only` still copies no media
- `copy_media` copies only reviewed media-backed examples
- unreviewed media is skipped
- privacy and ignore media is skipped
- missing or stale media is skipped
- unsupported media is skipped
- copied files land under ignored export paths
- path traversal is blocked
- manifest examples reference copied media paths
- `dry_run` writes no media
- no `ReviewLabel`, Event, or Visit truth writes occur
- no model files are generated
- no training dependency is required

## Implementation Plan

Tentative product-first phases:

- Phase 9X: media-copy export dry-run implementation.
- Phase 9Y: external training workspace checklist.
- Phase 9Z: external training workspace template docs.
- Next likely phase: Phase 10A — return to stream/source playback contract.
- Later: media-copy export implementation, still no training, or custom
  classifier runtime boundary.

These phases should keep reviewed corrections, local storage safety, and the
truth boundary ahead of training or runtime work.

## Explicit Non-Goals

- no actual media copying in this phase
- no media decoding
- no crop generation
- no thumbnail generation
- no training
- no model dependencies
- no model files
- no SpeciesNet runtime
- no custom classifier runtime
- no automatic labels
- no reviewed truth from suggestions
- no cloud upload
- no production accuracy claims
