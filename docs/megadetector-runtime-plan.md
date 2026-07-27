# MegaDetector Runtime Plan

## Decision

Phase 25 retains the explicit saved-frame adapter and adds one bounded
desktop-only live-monitor seam: an already-cached, privacy/Ignore-masked
ordinary-Zone crop may enter the same official `megadetector` adapter through a
single latest-frame worker. The executable path uses the official
`megadetector` Python package and an explicit local MDv5 `.pt` file, isolated
behind the `detector-megadetector` optional dependency.

The fallback path is the existing unavailable-safe MegaDetector wrapper. If the dependency is not installed or the model path is not configured, MockingBird must keep starting normally and report the adapter as unavailable or not configured.

ONNX is not the first implementation path unless MockingBird already has a local compatible MegaDetector ONNX artifact and a proven output mapping. For now, ONNX remains a possible later optimization path, not the primary route.

The adapter implements bounded, explicit image inference. The live seam has no
camera or network access: the camera session owns frame acquisition and hands
it a masked Zone JPEG. It has one active inference and one replaceable waiting
job; late results are discarded. It adds no model files, automatic downloads,
or truth creation.

Review-candidate runs decode the existing saved best frame and, when measured
motion bounds are available, apply a padded activity focus in memory. Detector
boxes are remapped to full-frame normalized coordinates. Zone geometry remains
review/scoring context and never supplies crop geometry or filters normal-Zone
proposals. Privacy and Ignore Zones still suppress inference. When measured
activity bounds are unavailable, inference uses the full frame. The original
media remains unchanged and no derived crop file is created.

Before any local runtime smoke test, follow [megadetector-local-setup.md](megadetector-local-setup.md) to keep model files ignored and outputs evidence-only.

Phase 7K's PyTorch-Wildlife path remains archived. The Phase 23 checkpoint in
[megadetector-runtime-findings.md](megadetector-runtime-findings.md) selects the
smaller official package path instead; it does not reopen PyTorch-Wildlife.

The product flow remains [stream-motion-trigger-plan.md](stream-motion-trigger-plan.md):
stream -> Zones -> bounded local object track or motion fallback -> one
high-resolution still/crop -> reviewable Visit -> user correction truth.

## Why This Runtime Path

MegaDetector-family detection remains product-aligned because it can produce animal, person, and vehicle evidence for outdoor activity review.

The official package exposes a stable MDv5 image API and accepts a full local
model path. MockingBird rejects aliases, requires an existing `.pt` file, passes
an absolute path, and explicitly disables forced model download. The runtime is
still optional, lazy, and isolated; the core API and frontend start without it.

## Dependency Plan

The `detector-megadetector` extra contains `megadetector>=10.0.22,<11.0` for
Python versions supported by that package. It is not part of the core install.
The checkpoint reviewed the official package API, top-level license, declared
dependency shape, and model-alias download behavior. Final redistributable
installer approval still requires a release-time transitive license and package
audit.

The core MockingBird install must not require MegaDetector, PyTorch-Wildlife, or
their heavy runtime stack. No model runtime dependency is imported at app
startup. Runtime imports happen lazily inside the explicit adapter execution
path.

If a dependency is missing, adapter status and run errors must explain the unavailable runtime clearly. Missing dependency must not crash app startup, local data status, exports, analytics, or normal review flows.

ONNX/local-weight-only remains a later optimization candidate if a compatible
artifact and stable output mapping become available.

## Model File Plan

No model files are committed. MockingBird does not download model files
automatically. Model aliases are rejected; the adapter accepts an existing local
MDv5 `.pt` file only in this slice.

The model path must be explicit local configuration:

- `MOCKINGBIRD_MEGADETECTOR_MODEL_PATH`
- `MOCKINGBIRD_MEGADETECTOR_LABELS_PATH` optional
- `MOCKINGBIRD_MEGADETECTOR_CONFIDENCE_THRESHOLD` optional

Model files should live outside Git-tracked source, for example under `data/models/` or another local ignored path. The `data/` directory remains ignored.

The initial approved artifact is `MDv5a.0.1` from
`https://github.com/agentmorris/MegaDetector/releases/download/v5.0/md_v5a.0.1.pt`.
Its required SHA-256 and MIT provenance are pinned in the adapter; any other
bytes fail closed before inference.

## Initial Media Scope

The first runtime implementation is limited to saved or imported image media:

- `image/jpeg`
- `image/png`
- `image/webp`

It must not process video, extract frames, read live streams, add source/camera
adapters, or run automatically. The existing Review Queue identification action
can explicitly analyze the candidate's saved best frame.

Review Queue triage may group already-loaded proposal evidence into animal,
vehicle/person, no-clear-proposal, and not-yet-checked views. It may also expose
the existing explicit saved-frame analysis action more prominently. These are
review-ordering aids only: opening the page or changing a filter never runs the
adapter, and proposal evidence never rejects, corrects, or reviews an item.

When a proposal includes a bounding box, Review Queue may overlay that box on
the original saved frame so reviewers can see what the analyzer labeled. The
overlay uses the latest proposal run for that displayed frame, uses remapped
full-frame coordinates, stays visually distinct from the measured activity
focus, and remains evidence only. Mixed animal and vehicle/person evidence must
stay visible rather than being presented as one unqualified classification.

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

## Implemented Validation Contract

The implementation proves:

- app starts without the optional dependency installed
- adapter appears as not configured or unavailable by default
- no model file is required for normal tests
- missing dependency path is tested
- configured model path with missing file is tested
- mocked successful MegaDetector output creates proposals only
- conversion, correction, and export truth flow still works
- raw detector output does not alter coverage or QA truth
- no model artifacts are tracked
- only an existing MDv5 `.pt` path is accepted
- the runtime loader receives an absolute local path and
  `force_model_download=False`
- official category IDs map to animal/person/vehicle evidence, with unknown and
  below-threshold detections dropped
- malformed output and runtime failure return clean errors before a run or truth
  record is written
- runtime caches stay under ignored local storage and package auto-install hooks
  are disabled before the optional runtime import
- measured-activity focus preserves full-frame proposal coordinates without
  deriving the focus from Zone geometry
- normal Zones remain proposal context; Privacy and Ignore Zones still suppress
  inference, and missing activity bounds fall back to full-frame inference

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
- no automatic rejection of motion candidates
- no automatic Review Queue analyzer run
