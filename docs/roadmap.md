# MockingBird Roadmap

## Phase 0 — Product foundation

Goal: establish the doctrine, repo shape, vocabulary, and product boundaries.

Deliverables:

- README
- product doctrine
- roadmap
- glossary
- architecture notes

Validation:

- The repo clearly presents MockingBird as a local-first outdoor video intelligence platform.
- Streams, zones, events, review, corrections, exports, and analytics are central.
- Source adapters are described as underneath the product.

## Phase 1 — Core product model and API

Goal: define the universal local-first event platform before building source adapters.

Core concepts:

- CameraSource
- Stream
- Zone
- Event
- Visit
- Detection
- Snapshot
- Clip
- ReviewLabel
- SpeciesCorrection
- DatasetExport

Validation:

- Seed/demo data can represent outdoor visits and events without relying on a real camera.
- API can list sources, streams, zones, events, visits, labels, and exports.
- The frontend can be built against stable product-shaped objects.

## Phase 2 — Stream-first frontend MVP

Goal: create the app shell around streams and reviewable outdoor events.

Core screens:

- Dashboard
- Streams
- Stream Detail
- Zone Editor
- Events
- Event Detail
- Review Queue
- Analytics
- Dataset Exports
- Settings

Validation:

- User can see a demo stream placeholder.
- User can draw or manage zones.
- User can review demo events.
- User can correct labels/species.
- User can see analytics derived from reviewed events.

## Phase 3 — Local media and demo source adapters

Goal: bring media into the platform without letting adapters define the product.

Initial adapters:

- Demo stream adapter
- Manual upload adapter
- Local folder import adapter

Validation:

- Imported media becomes streams/events/visits in the same product model.
- Review and correction flow works the same regardless of source.

## Phase 4 — Detection pipeline

Goal: analyze video/media for outdoor activity and create reviewable events.

Initial detection targets:

- bird
- squirrel
- cat
- dog
- person
- vehicle
- unknown_animal
- unknown_bird

Validation:

- Detections create reviewable events.
- User corrections override model guesses.
- Corrections are stored as dataset-grade labels.

## Phase 5 — Bird feeder species vertical

Goal: make backyard bird feeder review genuinely useful.

Initial species targets:

- northern_mockingbird
- carolina_wren
- mourning_dove
- american_robin
- northern_cardinal
- blue_jay
- tufted_titmouse
- carolina_chickadee
- house_finch
- eastern_bluebird
- red_bellied_woodpecker
- downy_woodpecker
- brown_thrasher
- gray_catbird
- unknown_bird

Validation:

- Bird visits are reviewable by species.
- Corrections can generate clean local dataset exports.
- Analytics can summarize species and feeder activity over time.

## Phase 6 — Broader outdoor intelligence

Goal: expand beyond feeder review into yard-scale outdoor events.

Targets:

- wildlife activity
- pets
- cats
- squirrels
- people
- vehicles
- feeder zones
- birdbath zones
- driveway zones
- privacy zones
- ignore zones

Validation:

- MockingBird can describe meaningful yard activity over time.
- Events remain reviewable and correctable.
- Exports and analytics remain local-first.

## Phase 7 — Local model adapter readiness

Goal: prepare the first real local detector without weakening the review and truth boundary.

Current guardrail work:

- Phase 7D: model selection and runtime guardrails.
- Phase 7E: MegaDetector-family detector decision record.
- Phase 7F: MegaDetector adapter wrapper and unavailable-safe runtime path.
- Phase 7G: MegaDetector runtime selection and dependency plan.
- Phase 7H: optional MegaDetector dependency/runtime integration boundary.
- Phase 7I: MegaDetector local runtime setup checklist.
- Phase 7J: MegaDetector/PyTorch-Wildlife runtime smoke findings.
- Phase 7K: detector runtime pivot and motion trigger plan.
- Next likely phase: Phase 8A or 7L — zone-aware motion trigger backend design/implementation.

Validation:

- Model adapters produce proposal evidence only.
- User corrections remain dataset truth.
- Adapter evaluation and rollback stay local, reviewable, and safe.
- Real MegaDetector runtime work follows [megadetector-runtime-plan.md](megadetector-runtime-plan.md) before dependencies or inference behavior are added.
- Local MegaDetector setup follows [megadetector-local-setup.md](megadetector-local-setup.md) before any smoke test.
- PyTorch-Wildlife/MegaDetector remains an experimental archived runtime option pending dependency, license, and download-behavior review.
- The active next path is [stream-motion-trigger-plan.md](stream-motion-trigger-plan.md): stream -> zones -> motion trigger -> snapshot evidence -> later species suggestion -> user correction truth.

## Phase 8 — Zone-aware motion trigger foundation

Goal: build the lightweight stream-first event trigger path around user-drawn zones while preserving review and correction as truth.

Current work:

- Phase 8A: deterministic zone-aware motion scoring foundation for supplied grayscale frame planes.
- Phase 8B: explicit motion evaluation API contract for synthetic/manual frame-plane inputs.
- Phase 8C: Motion Evidence product design for bridging candidate motion to later Event/Visit evidence.
- Phase 8D: MotionEvidence schema/repository/API foundation.
- Phase 8E: MotionEvidence promotion design.
- Phase 8F: MotionEvidence promotion API/repository implementation.
- Phase 8G: MotionEvidence review surface.
- Phase 8H: manual MotionEvidence creation UI/dev surface.
- Phase 8I: frame sequence motion-to-evidence backend contract for already-sampled frame planes.
- Phase 8J: sampled-frame ingestion boundary design.
- Phase 8K: sampled-frame evaluation browser harness.
- Phase 8L: lightweight sampler abstraction design.
- Phase 8M: sampler abstraction code using supplied in-memory frame planes only.
- Phase 8N: best-frame media attachment design.
- Phase 8O: best-frame attachment schema/API compatibility review.
- Phase 8P: local frame artifact design.
- Phase 8Q: attach existing MediaAsset to MotionEvidence.
- Phase 8R: Motion Evidence media preview polish.
- Phase 8S: media-backed MotionEvidence creation from existing MediaAsset.
- Phase 8T: end-to-end motion/media review demo polish.
- Next likely phase: Phase 8U — local frame artifact creation from existing imported media or controlled frame capture design.

Validation:

- Motion scoring stays pure and deterministic.
- Motion evaluation API does not persist data or create product truth.
- Motion Evidence design preserves pending/promoted/ignored evidence as separate from truth.
- MotionEvidence creation and ignore actions do not create Event, Visit, ReviewLabel, export, or analytics truth.
- MotionEvidence promotion design keeps Event/Visit creation unreviewed and evidence-only until user correction.
- MotionEvidence promotion creates only unreviewed Event/Visit evidence and leaves correction/export truth untouched.
- MotionEvidence review surface lets users inspect, ignore, and promote evidence without creating truth.
- Manual MotionEvidence creation lets the browser exercise the evidence loop before stream sampling without creating truth.
- Frame sequence evaluation can create pending MotionEvidence from caller-provided frame planes without creating truth.
- Sampled-frame ingestion design defines the bridge from visible streams to frame planes before implementation.
- Sampled-frame evaluation harness exercises supplied frame planes in the browser without real stream sampling.
- Lightweight sampler abstraction design defines future sampler inputs, outputs, zone/privacy behavior, and truth boundary before implementation.
- Sampler abstraction code evaluates supplied in-memory frame planes and can create pending MotionEvidence without creating truth.
- Best-frame media attachment design defines how candidate frame indexes can later link to optional visible evidence without creating truth.
- Best-frame attachment compatibility confirms MotionEvidence and Visit/detail media references stay evidence-only.
- Local frame artifact design separates scoring frame planes from optional visual evidence references.
- Existing MediaAsset attachment lets pending MotionEvidence carry visual evidence context without creating truth.
- Motion Evidence media preview polish makes attached MediaAsset context visible without capture, decoding, thumbnails, model calls, or truth writes.
- Media-backed MotionEvidence creation lets manual pending evidence start with existing MediaAsset context without capture, decoding, thumbnails, model calls, or truth writes.
- End-to-end motion/media review demo polish makes the current import -> media-backed MotionEvidence -> preview -> promote -> review/correction loop easier to validate without capture, decoding, thumbnails, model calls, or truth writes from MotionEvidence.
- Stream sampling, media decoding, and species suggestion remain later phases.
- Motion output remains candidate evidence only; user correction remains dataset truth.

## Phase 9 — Species suggestion assistance

Goal: add species assistance as review evidence without weakening user correction as dataset/export truth.

Current work:

- Phase 9A: species suggestion adapter design.
- Phase 9B: SpeciesSuggestion schema/repository/API foundation.
- Phase 9C: SpeciesSuggestion UI surface with manual/mock suggestions.
- Phase 9D: species suggestion correction-flow design.
- Phase 9E: SpeciesSuggestion use-as-correction UI prefill.
- Phase 9F: SpeciesSuggestion status polish after successful correction.
- Phase 9G: Visit Detail species suggestion surface polish.
- Phase 9H: mock species suggestion adapter for existing Visits.
- Phase 9I: SpeciesNet runtime investigation docs.
- Phase 9J: SpeciesNet source/license/runtime review.
- Phase 9K: SpeciesNet optional adapter boundary plan.
- Phase 9L: review/species suggestion UI polish.
- Phase 9M: custom bird classifier dataset/export plan.
- Phase 9N: dataset export manifest design for classifier training.
- Phase 9O: classifier readiness report/API.
- Phase 9P: classifier readiness UI surface.
- Phase 9Q: classifier training manifest preview/API implementation foundation.
- Phase 9R: classifier manifest UI/download preview.
- Phase 9S: classifier manifest file export design.
- Phase 9T: manifest file export backend implementation, metadata files only.
- Phase 9U: classifier manifest export UI/status.
- Phase 9V: external training workflow documentation.
- Next likely phase: Phase 9W — media-copy export design or external training
  workspace checklist.

Validation:

- Species suggestions remain evidence only.
- SpeciesSuggestion stays separate from MotionEvidence, DetectionProposal, and ReviewLabel.
- SpeciesNet and custom bird classifiers remain optional future adapters, not product architecture.
- SpeciesNet is a candidate with a boundary plan; no runtime is selected or installed.
- Suggestions do not create reviewed labels, reviewed Visit/Event state, export truth, dataset coverage truth, or analytics truth without explicit user correction.
- Phase 9L stays product-first by improving review clarity and suggestion usability before adding classifier runtime.
- Phase 9M defines reviewed-data requirements before any custom classifier training or runtime work.
- Phase 9N designs the classifier-training export manifest around reviewed media-backed examples, taxonomy, split, skip, and quality signals.
- Phase 9O keeps the readiness path read-only, local, reviewed-truth-only, and free of export generation, model runtime, or training dependencies.
- Phase 9P makes readiness visible in the UI without creating exports, labels, datasets, or classifier/runtime behavior.
- Phase 9Q implements the read-only manifest preview/API foundation without training, media copying, manifest files, model files, or classifier runtime.
- Phase 9R adds the frontend manifest preview and browser-side JSON copy/download without server-side file export, media copying, training, or runtime behavior.
- Phase 9S defines the file-export boundary before any generated manifest files or reviewed media-backed example export work.
- Phase 9T implements metadata-only manifest file export without media copying, training, model files, runtime calls, or truth writes.
- Phase 9U adds dry-run/create UI and status for metadata export without media copying, training, model files, runtime calls, or truth writes.
- Phase 9V defines the external training workspace boundary without adding media copying, training dependencies, model files, runtime calls, or truth writes.
- Accepted/rejected/superseded suggestion status remains evidence workflow, not dataset truth.
- The Species Suggestions UI can create manual/mock evidence, inspect context, and update status without creating truth.
- Applying suggestion evidence must route through explicit review/correction before dataset/export truth changes.
- Use-as-correction prefill helps users start the existing correction form without creating truth until submit.
- Suggestion accepted status from use-as-correction is evidence metadata and happens only after correction submit succeeds.
- Visit Detail can show Visit-linked SpeciesSuggestions near correction without creating truth.
- Mock species suggestion generation creates pending evidence only and does not run a model or inspect media.
- Media-backed Event/Visit evidence can be the future input to suggestion adapters.
- SpeciesNet remains under investigation as an optional future suggestion adapter; no runtime, model files, or dependency changes happen before source/license/runtime review.
- SpeciesNet source review recommends boundary planning next, while runtime dependencies, model files, and downloads remain deferred.
- Custom classifier training depends on reviewed local exports; raw suggestions, MotionEvidence, DetectionProposal, and unreviewed Visits are not training truth.
