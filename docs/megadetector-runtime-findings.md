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

Approved local-artifact provenance for the current MDv5 path:

- version: `MDv5a.0.1`
- official source record: `agentmorris/MegaDetector` user guide
- official artifact URL:
  `https://github.com/agentmorris/MegaDetector/releases/download/v5.0/md_v5a.0.1.pt`
- recorded repository license: MIT
- SHA-256: `FE3E90E4B1955821AB7C1F88B446DC0C8CB25E109FDD1872916A55305294A5EF`

The adapter accepts an explicit existing `.pt` path only. Before an actual run,
it streams the local file through SHA-256 and fails closed on a mismatch; it
does not infer, create proposals, or attempt a replacement download. The
artifact itself remains an explicit user-approved, ignored local file.

Official references reviewed:

- [MegaDetector repository](https://github.com/agentmorris/MegaDetector)
- [MegaDetector user guide](https://github.com/agentmorris/MegaDetector/blob/main/megadetector.md)

## Phase 23 Local MDv5a Field Smoke

The first Windows field smoke used:

- `megadetector` 10.0.24 in MockingBird's optional `.venv312` install
- PyTorch 2.13.0 CPU runtime; no CUDA replacement or camera session
- official `md_v5a.0.1.pt`, 280,767,041 bytes
- local SHA-256
  `FE3E90E4B1955821AB7C1F88B446DC0C8CB25E109FDD1872916A55305294A5EF`
- default proposal threshold 0.1

The first load exposed user-profile cache writes from YOLOv5/Matplotlib. The
adapter now directs those caches to ignored `data/runtime/megadetector` storage
and disables YOLOv5 package auto-install before importing the runtime.

Observed inference results:

- full overexposed feeder frame: six vehicle detections from the street, no
  animals, 14.9 seconds including CPU model load
- the same frame with existing padded Red feeder focus: zero detections, 10.4
  seconds, so background vehicles no longer polluted feeder evidence
- actual Review Queue identification path on that candidate: `no_proposal`, no
  proposal IDs, no truth/export creation, 10.0 seconds
- official Orinoquía positive-control image: one animal at 0.952 confidence,
  10.3 seconds

The result validates real local inference and the evidence boundary; it does not
establish bird recall. The next field decision requires representative saved
frames that visibly contain feeder birds.

## Daylight Feeder Field Result

A later 4K daylight frame (`media-asset-007`) visibly contained a small bird on
the Tube feeder. The configured 0.10 threshold produced no proposal. A one-off
0.01 diagnostic did not justify lowering the product threshold: MDv5a scored the
empty feeder hook as `animal` at 0.091 and weakly labeled the visible bird as
`person` at 0.038. The original Tube feeder Zone was also shifted left of the
current camera framing and excluded most of the feeder and bird.

After realigning both feeder Zones, live motion completed the intended product
handoff and created `visit-motion-004` with one saved best frame. That particular
motion was a passing car behind the feeder, not a bird. The normal Review Queue
identification action correctly added a `vehicle` proposal at 0.825 confidence
without creating reviewed truth or export data.

This result validates camera -> Zone motion -> best frame -> Review Queue ->
MegaDetector proposal evidence on real field media. It also shows that the next
recall work is better exposure/framing plus more representative bird frames,
not a blanket MDv5 confidence reduction.

### Overexposure cleanup matrix

The same real bird frame was evaluated with the original image, reduced
brightness, gamma correction, contrast adjustment, and autocontrast across the
existing detector focus and two tighter Zone crops. The useful result was
spatial, not cosmetic:

- the existing broad focus scored the visible bird as `person` at 0.014
- the tighter Zone focus scored it as `person` at 0.462
- gamma correction increased that wrong `person` score to 0.570

The app therefore does not add a blanket cleanup filter. Highlight clipping has
already discarded detail, and tone adjustment can make wrong evidence more
confident. The tighter-Zone result was useful diagnostic evidence that framing
matters, but Zone geometry is scene data rather than analyzer crop geometry.
The product implementation instead measures changed-pixel bounds from the best
motion frame pair, pads that activity focus in memory, and uses the full frame
when those bounds are unavailable. Normal Zones remain scoring/review context;
Privacy and Ignore Zones still suppress analysis. The original best frame
remains unchanged for review and correction, and every model result remains
proposal evidence only.

The next image-quality step is a read-only camera-driver exposure capability
probe, followed by bounded hardware exposure calibration only on devices that
explicitly support it. Software filtering is not a substitute for preventing
clipping at capture time.

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
