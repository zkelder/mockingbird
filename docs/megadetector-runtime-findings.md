# MegaDetector Runtime Findings

## Purpose

This record captures the local PyTorch-Wildlife / MegaDetector smoke probe so MockingBird can keep the learning without making that runtime the product architecture.

MegaDetector remains useful as a detector/proposal adapter later. It is not the center of MockingBird's stream, zone, event, review, correction, export, and analytics loop.

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

Until that checkpoint is complete, PyTorch-Wildlife should stay archived as an experimental MegaDetector runtime path.

## Implementation Impact

PyTorch-Wildlife is not the active first implementation path.

The active path pivots to:

stream -> zones -> lightweight motion trigger -> snapshot evidence -> reviewable visit/event evidence -> later species suggestion -> user correction truth.

MegaDetector can return later as optional detector enrichment for boxes, blank filtering, or proposal quality. ONNX/local-weight-only remains a serious fallback candidate for a product-grade detector runtime.

## Recommended Future Checkpoint

Before reopening PyTorch-Wildlife integration, require:

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
