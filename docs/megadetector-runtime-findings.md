# MegaDetector Runtime Findings

## Purpose

This record captures the local PyTorch-Wildlife / MegaDetector smoke probe so MockingBird can keep the learning without making that runtime the product architecture.

MegaDetector remains useful as a detector/proposal adapter later. It is not the center of MockingBird's stream, zone, event, review, correction, export, and analytics loop.

## Phase 23 Official-Package Checkpoint

The earlier findings below apply to the archived PyTorch-Wildlife path. A July
2026 review of the official `agentmorris/MegaDetector` project found a narrower
route through the official `megadetector` package:

- the package exposes an MDv5 image loader and detector API
- MDv5 output uses stable category IDs for animal, person, and vehicle
- a full local `.pt` path can be passed to the loader
- known aliases may trigger model acquisition, so MockingBird rejects aliases
  and accepts existing local `.pt` files only
- the package remains a heavy optional model stack and is not part of core app
  startup

This checkpoint is sufficient for an optional, local, explicit inference slice.
It is not a release-time approval to bundle weights or redistribute the full
dependency tree. PyTorch-Wildlife remains archived.

Current implementation rules:

- lazy import `megadetector` only during an explicit adapter run
- pass a resolved local model path with `force_model_download=False`
- process one saved/imported image at a time
- default to a recall-oriented 0.1 evidence threshold, locally configurable
- cap retained proposals at 20
- create `DetectionProposal` evidence only

Official references reviewed:

- [MegaDetector repository](https://github.com/agentmorris/MegaDetector)
- [MegaDetector user guide](https://github.com/agentmorris/MegaDetector/blob/main/megadetector.md)

## Probe Boundary

The probe was local and disposable. It did not add runtime code, model files, model downloads, camera/source adapters, background workers, or product API changes.

The scratch environment was kept outside the repo, and the repo stayed clean after the probe.

## Import Findings

PyTorch-Wildlife initially failed on missing `soundfile`.

After installing `soundfile`, it failed on missing `librosa`.

After installing `soundfile` and `librosa`, `PytorchWildlife` 1.3.0 imported successfully.

## API Findings

The import exposed these MegaDetector classes:

- `MegaDetectorV6`
- `MegaDetectorV6Apache`
- `MegaDetectorV6MIT`
- `MegaDetectorV5`

Constructors referenced Zenodo URLs. They should not be instantiated in MockingBird until download behavior is reviewed and explicitly controlled.

## Download Behavior Risk

MegaDetector constructors appear to know remote model URLs. That is a product and repo-safety risk because MockingBird must not download model weights automatically.

Any future use must prove that model paths are local, explicit, and download-free before an adapter can run.

## Dependency Weight Findings

The PyTorch-Wildlife path pulled a large dependency tree, including heavy runtime and UI-adjacent packages such as torch, CUDA packages, triton, ultralytics, yolov5, gradio, lightning, torchaudio, torchvision, and OpenCV.

That dependency weight is risky for a local-first product where the core app must remain easy to install, start, and validate without optional model runtimes.

## Licensing Risk Findings

`pip` metadata showed licensing concerns around transitive runtime dependencies. This needs a deliberate dependency/license review before PyTorch-Wildlife can be offered as a product-grade optional install.

PyTorch-Wildlife stays archived as an experimental MegaDetector runtime path.

## Implementation Impact

PyTorch-Wildlife is not the active implementation path.

The active path pivots to:

stream -> zones -> lightweight motion trigger -> snapshot evidence -> reviewable visit/event evidence -> later species suggestion -> user correction truth.

The official package now provides explicit Review Queue proposal enrichment for
saved best frames. It does not yet blank-filter, suppress, or automatically
promote motion candidates. ONNX/local-weight-only remains a later optimization
candidate.

## Recommended Future Checkpoint

Before reopening PyTorch-Wildlife integration or approving a redistributable
model installer, require:

- dependency tree review
- license review
- download behavior review
- local model-path-only proof
- app-start proof without optional runtime installed
- evidence-only proposal mapping proof
- rollback proof

## Truth Boundary Reminder

MegaDetector outputs are `DetectionProposal` evidence only.

They must never create reviewed labels, mark events or visits reviewed, create export-ready records, bypass Review Queue or Visit Detail correction, or become analytics/coverage truth without user correction.

## Rollback/Cleanup

Keep PyTorch-Wildlife out of core dependencies.

Remove or do not advertise optional extras until dependency/license/download behavior is reviewed.

Keep model artifacts ignored and outside source control. Existing proposals, if created by a future adapter, remain evidence records; reviewed corrections and exports remain intact.
