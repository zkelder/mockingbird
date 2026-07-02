# External Training Workspace Checklist

## Purpose

This checklist prepares a local external training workspace without adding
training dependencies, generated datasets, model files, or media-copy behavior
to core MockingBird.

It is an operator checklist for future classifier training preparation. It does
not implement tooling, media copying, training, model runtime, or generated
artifacts.

## Product Flow

reviewed corrections -> classifier readiness report -> manifest metadata export
-> copy-media dry run -> external training workspace preparation -> future
media-copy export -> external training/evaluation -> future optional classifier
adapter -> `SpeciesSuggestion` evidence -> user correction remains truth.

## Workspace Location Policy

- Workspace must live outside tracked source paths or under ignored local
  data/training paths.
- Never place a training workspace under `src/`, `docs/`, `tests/`, or `web/`.
- Generated datasets and model artifacts must not be committed.
- Workspace path should be explicit and user-controlled.
- Local-first only; no cloud upload happens by default.

## Pre-Flight Checklist

- [ ] Repo diff reviewed and expected before export/training prep.
- [ ] Classifier readiness report reviewed.
- [ ] Metadata manifest preview reviewed.
- [ ] Metadata export created.
- [ ] `copy_media` dry-run reviewed.
- [ ] Planned media count and byte estimates reviewed.
- [ ] Skipped media reasons reviewed.
- [ ] Privacy and ignore policy checked.
- [ ] Storage available for any future copied media bundle.
- [ ] Export/workspace path ignored by Git.
- [ ] No model files in repo.
- [ ] No training dependencies added to the core app.

## Required Inputs

- `manifest.jsonl` or preview JSON
- `taxonomy.json`
- `skipped_records.jsonl`
- `summary.json`
- optional `manifest.csv`
- local media references
- copy-media dry-run result
- target taxonomy/species list

## Optional Future Inputs

- copied media bundle
- `labels.txt`
- train/validation/test split files
- quality flag summaries
- per-species readiness reports
- model card template
- experiment notes

## Media-Copy Decision Checklist

- [ ] Is media copying necessary yet?
- [ ] Are examples reviewed and media-backed?
- [ ] Are privacy and ignore zones excluded?
- [ ] Are missing/stale media references handled?
- [ ] Is estimated size acceptable?
- [ ] Are unsupported media types skipped?
- [ ] Is output path ignored?
- [ ] Is cleanup plan known?

## Training Environment Checklist

The external workspace owns:

- Python/environment manager
- training dependencies
- GPU/CPU configuration
- augmentation tooling
- experiment tracking
- model checkpoint location
- evaluation reports
- model card/notes

Core MockingBird should not install these by default.

## Dataset Layout Checklist

Recommended future local layout:

```text
workspace/
  exports/
  media/
  manifests/
  experiments/
  models/
  reports/
  notes/
```

This is a recommendation, not an implementation.

## Privacy/Local-First Checklist

- [ ] No cloud upload by default.
- [ ] User owns exported files.
- [ ] Copied media remains local.
- [ ] Privacy and ignore zones respected.
- [ ] Cleanup/reset instructions required before implementation.
- [ ] Original filenames avoided when privacy-sensitive.

## Truth-Boundary Checklist

- Reviewed corrections are training truth.
- `SpeciesSuggestion` status is not truth.
- `MotionEvidence` is not truth.
- `DetectionProposal` is not truth.
- Training output is not truth.
- Future classifier output must create `SpeciesSuggestion` evidence only.
- User correction remains final truth.

## Evaluation Checklist

- examples per species
- train/validation/test split counts
- small-class warnings
- confusion matrix later
- per-class precision/recall later
- unknown/false-positive handling
- species lookalike notes
- local overfitting risk
- no production accuracy claims without evaluation

## Model Artifact Checklist

- No model artifacts in repo.
- Model checkpoints stay under ignored `workspace/models` or `data/models`.
- No `.pt`, `.pth`, `.onnx`, `.weights`, `.engine`, or `.ckpt` files are
  committed.
- Future runtime adapter requires explicit local model path.
- App starts without model installed.

## Return-To-MockingBird Checklist

Future return path:

- trained model reviewed externally
- optional adapter boundary plan
- lazy import/local model path
- mocked tests first
- classifier output creates `SpeciesSuggestion` only
- use-as-correction remains explicit

## Failure Cases

- not enough examples
- class imbalance
- missing media
- privacy-sensitive media
- storage pressure
- stale paths
- dependency conflicts
- bad training results
- model overfit
- unclear model license if external base model is used

## Recommended Next Phases

Recommendation: Phase 9Z should be external training workspace template docs
before actual media copying. That keeps the operator workflow, ignored paths,
cleanup expectations, and artifact boundaries clear before files are copied.

Other possible next phases:

- Phase 9Z: media-copy export implementation, still no training.
- Phase 10A: return to stream playback/source contract.

## Explicit Non-Goals

- no media copying in this phase
- no training in this phase
- no training dependencies
- no model files
- no generated dataset files
- no SpeciesNet runtime
- no custom classifier runtime
- no automatic labels
- no reviewed truth from suggestions
- no cloud upload
- no production accuracy claims
