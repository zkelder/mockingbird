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
- Next: Phase 7F — MegaDetector adapter implementation spike.

Validation:

- Model adapters produce proposal evidence only.
- User corrections remain dataset truth.
- Adapter evaluation and rollback stay local, reviewable, and safe.
