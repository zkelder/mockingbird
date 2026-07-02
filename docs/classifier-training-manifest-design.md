# Classifier Training Manifest Design

## Purpose

Define the future manifest contract for exporting stable, auditable,
reviewed media-backed examples for classifier training or evaluation.

Phase 9Q implements the first backend foundation as a read-only structured
manifest preview API. It still adds no training dependencies, model runtime,
generated dataset, media copying, or file export implementation to the core app.

## Product Flow

reviewed media-backed Visit -> ReviewLabel correction truth -> dataset quality
signals -> classifier training manifest export -> optional local media
copy/reference policy -> external training/evaluation -> future classifier
output -> SpeciesSuggestion evidence -> user correction truth.

## Manifest Truth Policy

Only reviewed user corrections are training truth.

The manifest must not treat these as truth:

- `SpeciesSuggestion`
- accepted suggestion status
- `MotionEvidence`
- `DetectionProposal`
- unreviewed Visit records
- unreviewed Event records

Exports should include skipped records with explicit skip reasons whenever an
eligible-looking record is not exportable.

Phase 9O adds a read-only classifier readiness report to summarize these
counts and warnings before any manifest export implementation is added.
Phase 9P adds the frontend readiness surface so those signals can guide future
manifest export decisions without generating export files.
Phase 9Q adds a read-only manifest response for reviewed media-backed examples,
skipped records, taxonomy metadata, split assignment, provenance, and summary
warnings. It writes no manifest files and creates no truth.
Phase 9R adds a frontend manifest preview with summary, examples, skipped
records, taxonomy, warnings, and browser-side JSON copy/download actions. It
still writes no server-side manifest files and creates no truth.
Phase 9S defines the future backend file-export boundary in
[classifier-manifest-file-export-design.md](classifier-manifest-file-export-design.md);
it is docs-only and still creates no files.
Phase 9T implements backend metadata file export under an ignored local path.
It writes manifest files only and still does not copy media, train, run
classifier runtime, or create truth.
Phase 9U adds frontend controls/status for dry-run and metadata export
creation. It keeps export UI separate from media copying, training, runtime, and
review truth.
Phase 9V documents the external training workflow boundary in
[external-training-workflow.md](external-training-workflow.md), keeping training
dependencies, model artifacts, and experiment output outside the core app.
Phase 9W defines the future optional media-copy export boundary in
[media-copy-export-design.md](media-copy-export-design.md). The current
implementation still supports reference-only metadata export.
Phase 9X adds copy-media dry-run planning so users can inspect planned local
media paths, skip reasons, and byte estimates before any actual media-copy
implementation.

## Manifest File Formats

Primary format: `manifest.jsonl`.

Use one JSON object per included training example. JSONL is streamable,
diffable, easy to validate, and preserves nested fields such as provenance,
quality flags, detection references, and media metadata without flattening loss.

Optional companion files:

- `manifest.csv` for spreadsheet review.
- `taxonomy.json` or `taxonomy.csv` for label metadata.
- `labels.txt` for simple trainer label lists.
- split assignment recorded in each manifest row and optionally summarized in
  `splits.json`.
- `skipped_records.jsonl` and a skip summary for records excluded from the
  export.

Phase 9Q does not create any of these files. It returns the same information as
JSON-friendly API data so export/download behavior can be designed separately.
Phase 9R can copy or download that already-loaded response in the browser as a
JSON preview. That browser action is not a server-side export and does not
create `manifest.jsonl`, `manifest.csv`, media copies, labels files, taxonomy
files, or skipped-record files in the app.
Future backend-generated files must follow
[classifier-manifest-file-export-design.md](classifier-manifest-file-export-design.md)
and remain metadata-only unless a later phase explicitly scopes media copying.

## Required Fields

Each included example should contain:

- `example_id`
- `visit_id`
- `event_id` nullable
- `media_asset_id`
- `source_id` nullable
- `stream_id` nullable
- `zone_id` nullable
- `local_media_path` or `exported_media_path`
- `label`
- `taxonomy_id`
- `common_name` nullable
- `scientific_name` nullable
- `reviewed_label_id` or `correction_id`
- `reviewed_at` nullable
- `created_at`
- `split`
- `quality_flags`
- `skip_reason` nullable
- `provenance`

## Optional Fields

Future manifests may add:

- `motion_evidence_id`
- `detection_proposal_ids`
- `species_suggestion_ids`
- `snapshot_media_asset_id`
- `representative_media_path`
- `copied_media_path` future media-copy extension
- `bbox` or crop reference nullable
- camera/source metadata summary
- `notes`
- `label_conflict_summary`
- `duplicate_group_id` future
- season/date bucket future

## Media Reference Policy

Initial manifest exports should reference local media paths or `MediaAsset`
IDs. Copying media into an export folder is a later implementation option and
must remain local and follow
[media-copy-export-design.md](media-copy-export-design.md).

No cloud upload is part of this plan.

Missing, unreadable, or stale media references should skip the example with
`missing_media` or `stale_media_reference`.

Privacy and ignore zone evidence should be excluded or explicitly flagged
according to the future export policy. Crops are future evidence references, not
required for the initial manifest.

## Initial Media Scope

The first implementation should use existing media-backed Visit examples and
their attached `MediaAsset` references. It should not decode media, extract
frames, create crops, capture streams, or generate new media artifacts.

## Output Mapping

The manifest maps reviewed product records to external training examples:

- Visit/Event context identifies the reviewed observation.
- `ReviewLabel` or correction context supplies truth.
- `MediaAsset` context supplies local media reference.
- taxonomy context supplies the normalized label.
- quality, skip, and provenance fields explain why the example is usable or
  excluded.

Future classifier output from a trained model must map back into
`SpeciesSuggestion` evidence only.

## Truth Boundary

The manifest can package reviewed truth for external training, but it cannot
make future model output truth. Any classifier trained from this manifest must
return suggestions that pass through the existing review/correction flow before
dataset, export, analytics, or reviewed Visit/Event state changes.

## Failure Behavior

Manifest generation should fail safely:

- skip unusable examples with specific reasons
- keep partial manifest records deterministic when safe
- never invent labels for missing truth
- never turn suggestion evidence into truth
- report summary warnings for low coverage, missing media, conflicts, and
  out-of-taxonomy labels

## Split Policy

Train/validation/test splits should avoid leakage.

Future implementation should prefer splitting by Visit, Event, Source, Stream,
or time bucket rather than by individual media file alone. It should avoid
placing near-duplicate frames from the same burst or visit in different splits.

Small datasets may use train/validation only until enough reviewed examples
exist for a meaningful test split.

Every export should record the split assignment, split policy, reproducible
seed, and configuration used.

## Skip Reason Policy

Supported skip reasons:

- `unreviewed`
- `missing_review_label`
- `unknown_label`
- `false_positive_policy_excluded`
- `missing_media`
- `stale_media_reference`
- `privacy_zone`
- `ignore_zone`
- `out_of_taxonomy`
- `conflicting_corrections`
- `insufficient_metadata`
- `duplicate_policy_excluded`
- `unsupported_media_type`

## Quality Flags

Quality flags are metadata, not truth. Suggested flags:

- `low_light`
- `blurry`
- `tiny_subject`
- `occluded`
- `multiple_subjects`
- `feeder_obstruction`
- `possible_duplicate`
- `label_conflict`
- `out_of_taxonomy`
- `unknown_label`
- `media_missing`
- `privacy_sensitive`

## Taxonomy Export

Each manifest export should include taxonomy metadata:

- taxonomy IDs
- common names
- scientific names when known
- aliases
- target species list
- unknown-label policy
- false-positive policy
- taxonomy version and provenance

The taxonomy export should make training labels reproducible and auditable
outside the app.

## Dataset Summary Report

Future exports should produce a summary report with:

- examples per species
- media-backed reviewed examples
- skipped counts by reason
- covered and missing target species
- unknown and false-positive counts
- per-zone and per-source counts
- split distribution
- quality flag counts
- readiness warnings

The Phase 9O readiness report gates manifest work by showing whether reviewed
media-backed species examples, taxonomy coverage, skip reasons, and quality
warnings are ready enough to proceed. The Phase 9P UI makes those signals
visible. Phase 9Q adds the backend manifest preview foundation while still
deferring file export, media copying, training, and runtime behavior.
Phase 9R makes the manifest preview visible in the app and supports browser-side
JSON copy/download for review before any generated dataset export exists.
Phase 9S documents the future file export policy for local metadata files only,
with media copying, training, and model runtime still deferred.
Phase 9T implements that backend metadata export path while keeping media
copying, training, and model runtime deferred.
Phase 9U makes dry-run and metadata export status visible in the manifest UI.
Phase 9V defines the next boundary: exported metadata may feed an external
workspace, but training and model artifacts stay outside core MockingBird.
Phase 9W defines how optional copied media could later join that workflow while
remaining local, ignored, and separate from reviewed truth.
Phase 9X implements dry-run media planning only; it writes no media files and
creates no export truth.

## Relationship To Existing Dataset And Export Features

Current exports support reviewed observations, dataset coverage, product
analytics, and local evidence review. The classifier training manifest is
training/evaluation oriented.

Both paths use reviewed correction truth. The classifier manifest adds split
assignment, quality flags, skip reasons, and taxonomy metadata for external
training workflows.

## Relationship To Future Custom Classifier

Training stays outside the core app or behind explicit future tooling. The core
app should not gain training dependencies from this design.

A trained custom classifier may later return `SpeciesSuggestion` evidence with
per-class performance metadata so readiness can be judged class by class. It
must not write `ReviewLabel`, reviewed Visit/Event state, export truth, dataset
coverage truth, or analytics truth.

## Test Plan For Implementation Phase

Future tests should prove:

- reviewed media-backed examples are included
- unreviewed records are skipped
- accepted `SpeciesSuggestion` alone is skipped
- `MotionEvidence` alone is skipped
- missing media is skipped
- privacy and ignore zone examples are excluded or flagged
- unknown and false-positive policy is applied
- conflicting corrections are flagged
- required fields are present
- taxonomy export is created
- split assignment is reproducible
- no model or training dependency is required
- no generated model files are created

Phase 9Q backend tests cover this foundation for the read-only API response,
including reviewed media-backed inclusion, skip reasons, taxonomy entries,
deterministic splits, read-only behavior, and evidence-not-truth boundaries.

## Rollback Plan

Manifest implementation should be easy to disable or remove:

- keep reviewed correction records unchanged
- keep media records unchanged
- keep classifier output separate as `SpeciesSuggestion` evidence
- allow export policy changes to regenerate manifests without rewriting truth
- delete generated manifest files without deleting reviewed product data

## Implementation Plan

Tentative product-first phases:

- Phase 9O: classifier-readiness report/API.
- Phase 9P: classifier readiness UI surface.
- Phase 9Q: classifier training manifest preview/API implementation foundation.
- Phase 9R: classifier manifest UI/download preview.
- Phase 9S: classifier manifest file export design.
- Phase 9T: manifest file export backend implementation, metadata files only.
- Phase 9U: classifier manifest export UI/status.
- Phase 9V: external training workflow documentation.
- Phase 9W: media-copy export design.
- Phase 9X: media-copy export dry-run implementation.
- Phase 9Y: media-copy export implementation, still no training, or external
  training workspace checklist.

These phases remain tentative. Manifest and readiness work should come before
training, runtime, or model integration.

## Explicit Non-Goals

- no generated dataset in this phase
- no manifest file export in Phase 9Q
- no media copying in Phase 9Q
- no server-side manifest file export or media copying in Phase 9R
- no file generation in Phase 9S
- no media copying in Phase 9T
- no media copying or training in Phase 9U
- no media copying in Phase 9W
- no actual media copying in Phase 9X
- no training
- no model dependencies
- no model files
- no SpeciesNet runtime
- no custom classifier runtime
- no automatic labels
- no reviewed truth from suggestions
- no cloud upload
- no production accuracy claims
