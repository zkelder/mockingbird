# External Training Workflow

## Purpose

MockingBird can export reviewed classifier metadata, but training dependencies,
dataset assembly, model checkpoints, and experiment artifacts must stay outside
the core app until an explicit future phase scopes them.

This document defines the external workflow boundary. It does not implement
training tooling, media copying, model runtime, scripts, or generated datasets.
Phase 9W defines the future optional media-copy boundary in
[media-copy-export-design.md](media-copy-export-design.md).
Phase 9Y adds the operator checklist in
[external-training-workspace-checklist.md](external-training-workspace-checklist.md).

## Product Flow

reviewed media-backed Visits -> classifier readiness report -> metadata
manifest export -> copy-media dry run -> external workspace checklist -> future
media-copy export -> train/evaluate outside core app -> future trained model
adapter -> `SpeciesSuggestion` evidence -> user correction remains truth.

## Core Boundary

- Core MockingBird stores review truth and local media references.
- Core MockingBird can export metadata manifests.
- Core MockingBird should not gain training dependencies by default.
- Core MockingBird should not commit datasets or model files.
- Core MockingBird should not treat model output as truth.

## External Workspace Concept

A future external workspace should live outside the repo or under an ignored
local path. It receives manifest metadata files from MockingBird and may receive
copied media only after a separate explicit media-copy phase.
Operators should use
[external-training-workspace-checklist.md](external-training-workspace-checklist.md)
before actual media copying or training setup.

The external workspace owns:

- training dependencies
- dataset assembly
- model checkpoints and outputs
- experiment logs and metrics
- model card notes
- cleanup of generated artifacts

Experiment artifacts should stay out of the core app.

## Inputs From MockingBird

Current or future inputs:

- `manifest.jsonl`
- `taxonomy.json`
- `skipped_records.jsonl`
- `summary.json`
- optional `manifest.csv`
- local media references
- split assignments
- quality flags
- provenance
- copy-media dry-run result

## Media Handling Boundary

Current classifier manifest export is metadata-only.

- Media copying is not implemented yet.
- Future media-copy export must follow
  [media-copy-export-design.md](media-copy-export-design.md).
- No cloud upload by default.
- Privacy and ignore zones must remain respected.
- Missing or stale media references should remain skip/warning cases.

## Training Responsibility

The external workflow owns:

- training environment
- dependency installation
- dataset assembly
- augmentation
- training/evaluation
- model checkpoint storage
- experiment logs
- metrics
- model card notes

The core app does not own these yet.

## Model Artifact Policy

- No model artifacts are committed.
- No checkpoints should be written under `src/`, `docs/`, `tests/`, or `web/`.
- Model files belong under ignored local model paths only.
- A future runtime adapter must require an explicit local model path.
- Model output returns `SpeciesSuggestion` evidence only.

## Evaluation Policy

Future evaluation should include:

- per-class metrics
- confusion matrix
- train/validation/test split reporting
- small-class warnings
- unknown and false-positive handling
- species lookalike notes
- local overfitting warnings
- no production accuracy claims without evaluation

## Returning Model Results To MockingBird

A future trained classifier may become an optional local adapter.

- The adapter runs locally.
- Output creates `SpeciesSuggestion` records.
- Suggestions appear in review.
- Use-as-correction requires explicit user correction submit.
- Correction remains truth.

## Relationship To SpeciesNet

SpeciesNet remains an optional external candidate. Custom classifier training is
a separate path. Both may output `SpeciesSuggestion` evidence in future phases,
and neither bypasses review/correction.

## Security/Privacy/Local-First Policy

- Local-first by default.
- No cloud upload by default.
- The user controls exported files.
- Privacy and ignore zones are respected.
- Export and training artifacts are local and ignored.
- Cleanup guidance is required before future implementation.

## Recommended Future Phases

Tentative product-first phases:

- Phase 9W: media-copy export design.
- Phase 9X: media-copy export dry-run implementation.
- Phase 9Y: external training workspace checklist.
- Phase 9Z: external training workspace template docs or media-copy export
  implementation, still no training.
- Later: custom classifier runtime boundary plan.

## Test Plan For Future Implementation

Future tests should prove:

- metadata export contains reviewed truth only
- media-copy export excludes privacy and ignore zones
- training artifacts are ignored by Git
- model files are not committed
- optional adapter starts unavailable when model path is missing
- mocked classifier output creates `SpeciesSuggestion` only
- no `ReviewLabel` or export truth is created from model output
- use-as-correction remains explicit

## Explicit Non-Goals

- no training in core app
- no training dependencies
- no model files
- no generated dataset files in this phase
- no media copying
- no SpeciesNet runtime
- no custom classifier runtime
- no automatic labels
- no reviewed truth from suggestions
- no cloud upload
- no production accuracy claims
