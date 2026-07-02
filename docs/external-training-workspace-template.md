# External Training Workspace Template

## Purpose

This template documents a recommended external training workspace layout without
adding generated datasets, training dependencies, copied media, or model
artifacts to core MockingBird.

It is documentation only. This phase does not create workspace folders, write
manifests, copy media, install training dependencies, train models, or add model
runtime behavior.

## Product Flow

reviewed corrections -> classifier readiness report -> metadata manifest export
-> `copy_media` dry run -> external workspace template -> future media-copy
export -> external training/evaluation -> future optional classifier adapter ->
`SpeciesSuggestion` evidence -> user correction remains truth.

## Recommended Location

- Preferred: outside the repo, such as `~/mockingbird-training-workspace`.
- Acceptable future option: an ignored local path under
  `data/training_workspaces/`.
- Never place the workspace under `src/`, `docs/`, `tests/`, `web/`, or tracked
  app paths.
- The user controls the workspace path.
- No cloud upload happens by default.

## Template Directory Tree

Recommended structure:

```text
mockingbird-training-workspace/
  README.md
  exports/
    metadata/
    dry-runs/
  manifests/
  media/
    copied/
    rejected/
  splits/
  experiments/
    runs/
    reports/
    notes/
  models/
    checkpoints/
    candidates/
  evaluation/
    confusion-matrices/
    per-class-metrics/
    examples/
  logs/
  cleanup/
```

This is documentation only. Phase 9Z does not create these folders.

## Directory Purposes

- `exports/metadata`: manifest export files from MockingBird.
- `exports/dry-runs`: `copy_media` dry-run JSON/status output.
- `manifests`: normalized training manifest versions.
- `media/copied`: future copied training media.
- `media/rejected`: intentionally excluded/problem examples, if ever useful.
- `splits`: train/validation/test split reports.
- `experiments/runs`: external training run directories.
- `experiments/reports`: human-readable training summaries.
- `experiments/notes`: experiment notes and decisions.
- `models/checkpoints`: raw training checkpoints.
- `models/candidates`: evaluated candidate models.
- `evaluation`: metrics, summaries, and example-level evaluation outputs.
- `logs`: external tooling logs.
- `cleanup`: deletion notes or cleanup manifests.

## Git And Artifact Policy

- The workspace should not be tracked by core MockingBird Git.
- No model artifacts belong in the core repo.
- No media bundles belong in the core repo.
- No generated datasets belong in the core repo.
- No `.pt`, `.pth`, `.onnx`, `.weights`, `.engine`, or `.ckpt` files belong in
  tracked paths.
- Future implementation should add ignored paths before writing files.
- If the workspace has its own Git repo, it should ignore media, models, and
  large generated artifacts by default.

## Suggested Workspace README Contents

- source MockingBird repo/commit
- export ID
- export timestamp
- media policy used
- dry-run result location
- dataset/species scope
- privacy/ignore confirmation
- storage estimate
- training environment notes
- evaluation summary
- model candidate path
- cleanup status

## Manifest Handoff Policy

- Metadata export files are copied or referenced into the workspace.
- `manifest.jsonl` remains canonical.
- `taxonomy.json` defines labels.
- `skipped_records.jsonl` documents excluded records.
- `summary.json` documents counts and warnings.
- Optional `manifest.csv` is convenience only.
- Future copied media paths should be added as explicit manifest fields, not
  inferred from folder names alone.

## Media Handoff Policy

- Current system supports dry-run planning only.
- Actual media-copy export remains future work.
- Future copied media should use safe `example_id`-based names.
- Original filenames should not be required.
- Privacy/ignore media is excluded.
- Missing, stale, or unsupported media is skipped.
- Video, crops, and thumbnails remain future decisions.

## Training Environment Policy

The external workspace owns:

- Python/runtime environment
- dependency installation
- GPU/CPU setup
- augmentation tooling
- experiment tracking
- training scripts/notebooks, if any
- model checkpoints
- reports/metrics

Core MockingBird does not own these by default.

## Evaluation Output Template

Expected future external artifacts:

- `per_class_metrics.json`
- `confusion_matrix.csv` or `confusion_matrix.json`
- `split_summary.json`
- `small_class_warnings.json`
- `example_errors.jsonl`
- `model_card.md`
- `evaluation_summary.md`

These are future external artifacts. Phase 9Z does not create them.

## Model Candidate Policy

- Candidate models live in `workspace/models/candidates` or another ignored
  local model path.
- No candidate model becomes active automatically.
- Future MockingBird adapter must require an explicit local model path.
- Model output returns `SpeciesSuggestion` only.
- App starts without model installed.

## Cleanup Policy

- Copied media can be large.
- Workspace should have cleanup notes.
- Repeated exports should be separable by export ID/date.
- Stale exports should be removable.
- Cleanup should never delete original MockingBird media unless explicitly
  designed later.
- Future UI/docs should warn before creating large bundles.

## Failure Cases

- insufficient species coverage
- class imbalance
- stale local media paths
- unsupported media
- privacy/ignore exclusions reduce data
- storage pressure
- dependency conflicts
- model license uncertainty
- overfitting
- poor generalization to new yards/cameras
- confusing accepted suggestions with truth

## Return-To-MockingBird Path

external model candidate -> explicit optional adapter boundary -> lazy runtime
import -> explicit local model path -> mocked adapter tests ->
`SpeciesSuggestion` records -> user use-as-correction -> `ReviewLabel` truth
only after explicit submit.

## Example Checklist Before Training

- [ ] Readiness reviewed.
- [ ] Manifest export created.
- [ ] `copy_media` dry-run reviewed.
- [ ] Privacy/ignore reviewed.
- [ ] Workspace path outside tracked repo.
- [ ] Storage available.
- [ ] Dependencies isolated.
- [ ] No model/media artifacts in core repo.
- [ ] Target species selected.
- [ ] Train/validation/test split understood.
- [ ] Evaluation plan written.

## Recommended Next Phases

Recommendation: Phase 10A should return to the stream/source playback contract
after Phase 9Z. The classifier/export groundwork is now deep enough, and the
product still needs stronger real stream/source flow before continuing deeper
classifier implementation.

Other possible future phases:

- Phase 9AA: actual media-copy export implementation, still no training.
- Phase 9AB: custom classifier runtime boundary design.

## Explicit Non-Goals

- no workspace folder creation
- no media copying
- no training
- no training scripts
- no training dependencies
- no model files
- no generated dataset files
- no SpeciesNet runtime
- no custom classifier runtime
- no automatic labels
- no reviewed truth from suggestions
- no cloud upload
- no production accuracy claims
