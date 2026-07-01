# MegaDetector Runtime Plan

## Decision

The first implementation path is PyTorch-Wildlife / MegaDetector-family integration, isolated behind an optional adapter dependency.

The fallback path is the existing unavailable-safe MegaDetector wrapper. If the dependency is not installed or the model path is not configured, MockingBird must keep starting normally and report the adapter as unavailable or not configured.

ONNX is not the first implementation path unless MockingBird already has a local compatible MegaDetector ONNX artifact and a proven output mapping. For now, ONNX remains a possible later optimization path, not the primary route.

Phase 7H adds the optional dependency boundary and lazy execution seam. It still does not add production inference, model files, or automatic downloads.

## Why This Runtime Path

MegaDetector-family detection is product-aligned because it can produce animal, person, and vehicle evidence for outdoor activity review.

PyTorch-Wildlife / MegaDetector is the most direct route for that detector family. The risk is dependency weight, so the integration must be optional, lazy, and isolated from the core app. The core API and frontend must start without the runtime installed.

## Dependency Plan

Future MegaDetector runtime dependencies must be optional, such as a `detector-megadetector` extra or similarly scoped install target.

The core MockingBird install must not require MegaDetector, PyTorch-Wildlife, or their heavy runtime stack. No model runtime dependency should be imported at app startup. Runtime imports should happen lazily inside the adapter execution path.

If a dependency is missing, adapter status and run errors must explain the unavailable runtime clearly. Missing dependency must not crash app startup, local data status, exports, analytics, or normal review flows.

## Model File Plan

No model files are committed. MockingBird must not download model files automatically.

The model path must be explicit local configuration:

- `MOCKINGBIRD_MEGADETECTOR_MODEL_PATH`
- `MOCKINGBIRD_MEGADETECTOR_LABELS_PATH` optional
- `MOCKINGBIRD_MEGADETECTOR_CONFIDENCE_THRESHOLD` optional

Model files should live outside Git-tracked source, for example under `data/models/` or another local ignored path. The `data/` directory remains ignored.

## Initial Media Scope

The first runtime implementation is limited to imported image media:

- `image/jpeg`
- `image/png`
- `image/webp`

It must not process video, extract frames, use live streams, add source/camera adapters, or run automatically. Runs are explicit user-triggered adapter executions.

## Output Mapping

MegaDetector output maps into `DetectionProposal` evidence:

- `animal` -> `unknown_animal` or `animal` proposal evidence
- `person` -> `person` proposal evidence
- `vehicle` -> `vehicle` proposal evidence
- confidence -> proposal confidence
- bounding box -> proposal `bbox`
- zone context -> selected/provided zone when available, otherwise null

MegaDetector output must not create species truth, reviewed labels, or export-ready records. Export-ready data starts only after user conversion and correction.

## Truth Boundary

MegaDetector output is evidence only.

It creates `DetectionRun` and `DetectionProposal` records. It never creates reviewed labels, bypasses Review Queue or Visit Detail, marks events or visits reviewed, or writes dataset truth directly.

User corrections remain dataset truth. Exports, coverage, QA, analytics, and adapter evaluation use corrected and reviewed labels as truth.

## Failure Behavior

Expected failure behavior:

- missing model path -> `not_configured` status and a clear 400 on run
- missing dependency -> `unavailable` status and a clear message
- unsupported media -> 400
- missing media file -> clear 404 or 400
- empty detector result -> completed run with zero proposals and a clear note, if the implementation supports completed empty runs
- unexpected runtime error -> safe error with no partial truth writes

Runtime failures must not create reviewed labels, reviewed visits, export records, coverage truth, QA truth, or analytics truth.

## Test Plan For Implementation Phase

Future implementation must prove:

- app starts without the optional dependency installed
- adapter appears as not configured or unavailable by default
- no model file is required for normal tests
- missing dependency path is tested
- configured model path with missing file is tested
- mocked successful MegaDetector output creates proposals only
- conversion, correction, and export truth flow still works
- raw detector output does not alter coverage or QA truth
- no model artifacts are tracked

## Rollback Plan

Rollback is local and data-safe:

- remove the model environment variable to disable runtime
- uninstall the optional dependency to return to unavailable state
- keep existing `DetectionProposal` evidence as reviewable history
- preserve reviewed corrections and exports
- keep camera/source behavior independent of MegaDetector availability

## Explicit Non-Goals

- no species classifier
- no video/frame extraction
- no live camera
- no background worker
- no automatic model downloads
- no bundled weights
- no cloud
- no production accuracy claims
