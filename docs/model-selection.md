# Model Selection

## Goal Of First Detector Spike

The first real local detector candidate should prove that MockingBird can turn configured local model output into useful proposal evidence while preserving user review and correction as truth.

It is a product safety spike, not a production accuracy claim.

Phase 7E selects a MegaDetector-family local image detector as a useful detector/proposal family. Phase 7K archives the PyTorch-Wildlife runtime path as experimental after dependency, license, and download-behavior findings. See [detector-decision-megadetector.md](detector-decision-megadetector.md), [megadetector-runtime-plan.md](megadetector-runtime-plan.md), and [megadetector-runtime-findings.md](megadetector-runtime-findings.md).

The active next event-trigger path is [stream-motion-trigger-plan.md](stream-motion-trigger-plan.md): stream -> zones -> lightweight motion trigger -> snapshot evidence -> later species suggestion -> user correction truth.

## Acceptable First Detector Type

The first candidate must be:

- imported image media only
- local-only execution
- object or animal proposal generation only
- `DetectionProposal` evidence only
- explicitly triggered through the existing model adapter run flow

Species classification, live input, and automatic background processing are out of scope for the first candidate. SpeciesNet or another species classifier is a separate future suggestion adapter, not the motion trigger itself.

## Model Candidate Requirements

A candidate model should:

- run from a local file configured by the user
- produce labels, confidence scores, and optional bounding boxes
- support a small, understandable target label set such as bird, squirrel, cat, person, vehicle, or unknown animal
- tolerate missing or incomplete label files by falling back to safe generic labels
- fail clearly when output shape is unsupported
- be removable without changing reviewed product data

MegaDetector-family animal/person/vehicle detection remains useful future proposal enrichment. It is no longer the active first implementation path. The next implementation path is zone-aware motion triggering, with species suggestion handled by a separate future adapter.

## Future Species Suggestion Candidates

SpeciesNet and a custom backyard bird classifier are future species suggestion candidates, not detector adapters and not truth writers.

Phase 9B adds the `SpeciesSuggestion` schema/repository/API foundation before any SpeciesNet or custom classifier runtime. Phase 9C adds a manual/mock UI surface for suggestion evidence and status workflow; it still adds no species runtime, model dependency, media inspection, or truth writing. Phase 9D defines the explicit correction-flow boundary for using suggestion evidence without making status updates into truth.

Phase 9H adds a mock species suggestion adapter for existing Visits before any
SpeciesNet or custom classifier runtime. It creates pending suggestion evidence
for the review loop only and does not inspect media, run a model, or create
reviewed truth.

Phase 9I investigates SpeciesNet runtime, dependency, licensing, model-file, and
output-mapping questions in
[speciesnet-runtime-investigation.md](speciesnet-runtime-investigation.md).
This does not select SpeciesNet as an implementation runtime yet.

They should follow [species-suggestion-adapter-design.md](species-suggestion-adapter-design.md):

- receive media-backed Event/Visit evidence, optional zone context, and optional crop context
- return ranked species or taxon suggestions with confidence/provenance when available
- remain optional and local
- avoid runtime dependencies until a dedicated implementation phase
- feed `SpeciesSuggestion`, not `ReviewLabel`, directly
- require user review/correction before dataset/export truth changes

## Dependency Rules

Prefer the existing unavailable-safe detector shell and the motion-trigger path first.

PyTorch-Wildlife / MegaDetector is archived as experimental until dependency, license, and download behavior are reviewed. Do not advertise or deepen that optional runtime by default.

Serious future detector runtime candidates:

- ONNX Runtime for local model execution, only after a compatible local MegaDetector artifact and output mapping are available
- local-weight-only MegaDetector-family runtime with explicit model paths and no downloads
- PyTorch-Wildlife only if a future checkpoint resolves dependency/license/download risk
- Pillow or numpy only when the explicit implementation phase proves they are needed

Avoid heavy or model-specific runtime stacks unless an explicit implementation phase justifies them. No PyTorch, TensorFlow, OpenCV, Ultralytics, YOLO package, MegaDetector package stack, BirdNET runtime, SpeciesNet runtime, or model dependency should be added by selection docs alone.

## Model File Rules

Model files are local configuration and must stay out of git.

MockingBird must not:

- commit model weights
- generate model artifacts into the repo
- download models automatically
- require a model file for app startup
- hide the configured/unconfigured state from the user

Use environment variables such as `MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH` and optional labels configuration such as `MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH`. MegaDetector runtime work should use `MOCKINGBIRD_MEGADETECTOR_MODEL_PATH`, optional `MOCKINGBIRD_MEGADETECTOR_LABELS_PATH`, and optional `MOCKINGBIRD_MEGADETECTOR_CONFIDENCE_THRESHOLD`.

## Supported Media Scope

The first candidate is limited to imported image media:

- `image/jpeg`
- `image/png`
- `image/webp`

Video, live stream input, camera input, and frame extraction are not part of this candidate.

## Output Mapping Requirements

Detector output must map into:

- `DetectionRun` for the adapter execution
- `DetectionProposal` for each evidence item

The adapter must set proposal fields conservatively:

- normalized label
- confidence
- optional bounding box
- stream and zone context from the media/request
- suggested event type such as `animal_visit`
- suggested subject/species only when safe

No raw model output should become reviewed labels, export records, or analytics truth without user correction.

## Confidence Threshold Rules

Use a conservative default threshold. Make threshold configuration explicit and local.

Low-confidence outputs should be dropped or left as low-confidence proposal evidence. They must not become review truth.

Confidence is evidence metadata. It is not a replacement for correction.

## Performance Expectations

The first candidate should be boring and bounded:

- run only when requested
- process one imported image at a time
- avoid startup work
- avoid long-running background work
- fail without corrupting product state

If runtime cost is unclear, prefer disabled or unavailable status over automatic execution.

## Evaluation Plan

Evaluate with product data, not model hype:

- create proposal evidence
- convert useful proposals into reviewable events/visits
- correct labels through the normal review flow
- export reviewed truth
- compare proposal labels to reviewed corrections through adapter evaluation
- watch dataset coverage and dataset QA for regressions

Unknown reviewed labels should be surfaced separately from match-rate denominator.

## Rollback Plan

Rollback must be safe:

- unset the local model path or mark the adapter unavailable
- keep already-created proposals as evidence
- preserve user corrections and exports as truth
- use adapter evaluation to identify noisy labels
- do not delete product data to undo a bad model candidate

## Explicit Non-Goals

The first real detector candidate must not add:

- species classification
- video frame extraction
- camera or live stream input
- background workers
- cloud services
- automatic model downloads
- committed model weights
- production accuracy claims
- adapter-specific product flows
