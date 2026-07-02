# Classifier Manifest File Export Design

## Purpose

MockingBird already has a read-only classifier manifest preview API and a
browser-side JSON preview download. Backend-generated manifest files need a
separate design because server-side file export introduces local path choices,
artifact cleanup, ignored-directory policy, and media-copy boundaries.

Phase 9S created this design contract. Phase 9T implements backend metadata
file export from the existing manifest preview. It writes manifest metadata
files only; it does not copy media, train models, add dependencies, or add
runtime behavior.
Phase 9U adds frontend controls/status for dry-run and metadata export creation
against that existing backend route. The UI does not add file download
endpoints, copy media, train models, or create reviewed truth.
Phase 9V documents the external training workflow boundary in
[external-training-workflow.md](external-training-workflow.md). Metadata export
is an input to that external workflow only; it is not training or model runtime.
Phase 9W documents the future optional media-copy boundary in
[media-copy-export-design.md](media-copy-export-design.md). Copy-media export is
design-only and not part of the current implementation.
Phase 9X implements `copy_media` dry-run planning only. Actual media copying
remains future work.

## Product Flow

reviewed media-backed Visit -> manifest preview API -> local manifest metadata
export -> external training/evaluation workflow -> future classifier output
returns `SpeciesSuggestion` evidence -> user correction remains truth.

## File Export Boundary

Backend export may write manifest metadata files only.

- Media copying is a separate future phase.
- Training happens outside the core app.
- Metadata export is an input to the external workflow, not training itself.
- No model files are generated.
- No image dataset folders are generated.
- Generated files must live under ignored local data/export paths.
- Export generation must not create review truth or change product records.

## Candidate Future Output Files

Possible future files:

- `manifest.jsonl`
- `manifest.csv`
- `taxonomy.json`
- `labels.txt`
- `skipped_records.jsonl`
- `summary.json`
- `README.txt` or `export-notes.md` if a later phase needs generated notes

Recommended initial minimal set:

- `manifest.jsonl`
- `taxonomy.json`
- `skipped_records.jsonl`
- `summary.json`

CSV, labels, and generated notes can wait until the manifest-only path is proven.

## Output Directory Policy

Phase 9T writes generated files under the ignored local directory
`data/classifier_manifest_exports/<export-id-or-timestamp>/`.

Rules:

- Never write generated export files under `src/`, `docs/`, `tests/`, or `web/`.
- Include a timestamp or export ID in each export directory.
- Do not place model files in the export directory.
- Do not copy media into the initial manifest-only export.
- Cleanup and reset behavior must stay explicit.
- Failed exports should not leave ambiguous partial directories.

## Artifact/Git Safety

Generated manifest/export files must not be committed.

- `.gitignore` covers `data/`, including classifier manifest export files.
- Tests must verify no generated files are created unless an explicit export
  endpoint is called.
- Export paths should be local-first and user-visible enough for cleanup.

## Media Policy

Manifest-only export references existing `MediaAsset` IDs and local paths.

- Media copying is deferred.
- Copied-media export needs a separate phase and safety checks.
- Missing or stale media references produce skip reasons.
- Privacy and ignore zones remain excluded or flagged by export policy.
- Export generation must not decode media, inspect real media files, or create
  derived media artifacts.

## API Shape

Phase 9T route:

`POST /api/classifier-training-manifest/exports`

Request:

- `include_csv: bool = false`
- `include_summary: bool = true`
- `split_seed: str | None = None`
- `output_name: str | None = None`
- `media_policy: "reference_only" | "copy_media"`
- `dry_run: bool = false`

Response:

- `export_id`
- `output_directory`
- `files`
- `examples`
- `skipped`
- `warnings`
- `created_at`
- `media_policy`
- `planned_media_files`
- `skipped_media`
- `total_planned_media_bytes`

Potential read routes, if consistent with existing export patterns:

- `GET /api/classifier-training-manifest/exports/{export_id}`
- `GET /api/classifier-training-manifest/exports`

The current implementation keeps non-dry-run export fixed to
`media_policy: "reference_only"`. `copy_media` is dry-run only in Phase 9X; see
[media-copy-export-design.md](media-copy-export-design.md).

## Dry-Run Behavior

`dry_run` returns what would be written while writing no files.

- Dry-run output should match the current preview API as closely as possible.
- Dry-run should report planned filenames, counts, warnings, and skipped reasons.
- Phase 9U uses dry-run for UI validation before any local files are created.
- Dry-run creates no export directories, files, media copies, labels, or truth
  records.

## Truth Boundary

File export uses reviewed correction truth only.

- `SpeciesSuggestion` status is not training truth.
- `MotionEvidence` is not training truth.
- `DetectionProposal` is not training truth.
- Export generation creates no `ReviewLabel` records.
- Export generation marks no Visits or Events reviewed.
- Export generation changes no dataset coverage truth.
- Future classifier output must return `SpeciesSuggestion` evidence and pass
  through review/correction before becoming truth.

## Split/Taxonomy Consistency

File export must use the same split logic as the preview API.

- `taxonomy.json` must match labels present in `manifest.jsonl`.
- `skipped_records.jsonl` must preserve skip reasons from the preview policy.
- `summary.json` must match examples, skipped records, labels, splits, and
  warnings.
- Split seed/configuration must be recorded when configurable.

## Failure Behavior

Implementation should fail safely for:

- invalid output path
- export directory already exists
- disk write failure
- missing media references
- no examples available
- taxonomy mismatch
- permission error
- partial file write cleanup

Avoid partial or ambiguous exports. Prefer writing into a temporary directory and
promoting it only after all files are complete and internally consistent.

## Test Plan For Implementation Phase

Tests should prove:

- `dry_run` writes no files
- manifest-only export writes expected files under an ignored data path
- no media files are copied
- no model files are generated
- manifest contents match the preview API
- `skipped_records.jsonl` matches skip reasons
- `taxonomy.json` contains manifest labels
- no `ReviewLabel`, Event, or Visit truth writes occur
- repeated export creates unique export directories
- invalid output path is rejected
- generated files are ignored by Git policy

## Relationship To Existing DatasetExport

If the existing `DatasetExport` product model supports export records well, a
future implementation may reuse it. If it does not fit, do not force broad model
changes.

Current dataset exports are product/review oriented. Classifier manifest export
is training/evaluation oriented. Both must use reviewed correction truth, and
neither should treat evidence or suggestions as truth.

## Implementation Plan

Implementation phases:

- Phase 9T: manifest file export backend implementation, metadata files only.
- Phase 9U: classifier manifest export UI/status.
- Phase 9V: external training workflow documentation.
- Phase 9W: media-copy export design.
- Phase 9X: media-copy export dry-run implementation.
- Phase 9Y: media-copy export implementation, still no training, or external
  training workspace checklist.

Keep these phases product-first: reviewed corrections, local artifact safety,
and clear export boundaries come before training or runtime work.

## Explicit Non-Goals

- no media copying
- no non-dry-run `copy_media` export
- no training
- no model dependencies
- no model files
- no SpeciesNet runtime
- no custom classifier runtime
- no automatic labels
- no reviewed truth from suggestions
- no cloud upload
- no production accuracy claims
