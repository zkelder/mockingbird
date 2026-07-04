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
- Phase 9W: media-copy export design.
- Phase 9X: media-copy export dry-run implementation.
- Phase 9Y: external training workspace checklist.
- Phase 9Z: external training workspace template docs.
- Follow-on phase: Phase 10A — stream/source playback contract.

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
- Phase 9W defines the optional copied-media bundle boundary without copying media, generating datasets, adding dependencies, training, runtime calls, or truth writes.
- Phase 9X implements copy-media dry-run planning without copying media, creating export directories/files for copied media, generating datasets, adding dependencies, training, runtime calls, or truth writes.
- Phase 9Y defines the external local training workspace checklist without adding media copying, generated datasets, training dependencies, model files, runtime calls, or truth writes.
- Phase 9Z documents the external training workspace template without creating folders, copying media, generating datasets, adding training scripts/dependencies, model files, runtime calls, or truth writes.
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

## Phase 10 — Stream/source playback foundation

Goal: make the stream-centered product honest about what can be shown before real
source adapters exist.

Current work:

- Phase 10A: stream/source playback contract for Stream Detail.
- Phase 10B: source connection/provider status contract.
- Phase 10C: source provider configuration contract/UI.
- Phase 10D: source setup review/status polish.
- Phase 10E: manual media provider integration polish.
- Phase 10F: stream/source UX consolidation.
- Next likely phase: Phase 11A — first real source adapter boundary design.

Validation:

- Known streams return product-level playback status.
- Known sources return product-level connection/provider status.
- Provider definitions return product-level setup contracts.
- Provider configuration stores safe metadata only.
- Source setup review combines configuration, connection readiness, and stream
  playback readiness without connecting to sources.
- Manual media provider setup points to explicit import/review workflows while
  live playback remains out of scope.
- Source/Stream UX presents setup review, provider configuration, connection
  readiness, playback status, zone editing, and manual import as one product
  flow without changing review/correction truth.
- Unknown streams return 404.
- Unknown sources return 404.
- Unknown provider keys are rejected.
- Demo and placeholder streams do not claim real live playback.
- Demo and not-configured sources do not claim real live playback.
- Configured future providers still do not claim real live playback.
- Zone editing remains central even when playback is not configured.
- Source connection status includes related Stream ids and safe field readiness
  lists without exposing provider internals.
- Source provider configuration redacts secret fields to configured/not-configured
  markers.
- Source setup review reports demo-ready, metadata-ready, needs-setup,
  future-adapter-required, or unavailable readiness without creating evidence or
  truth.
- Manual media imports can create reviewable Events/Visits through explicit
  import actions; corrections remain dataset/export truth.
- Playback status does not create MotionEvidence, Events, Visits, ReviewLabels,
  SpeciesSuggestions, exports, analytics truth, media files, model artifacts, or
  adapter runtime calls.
- Source connection status does not create MotionEvidence, Events, Visits,
  ReviewLabels, SpeciesSuggestions, exports, analytics truth, media files, model
  artifacts, or provider runtime calls.
- Source provider configuration does not create MotionEvidence, Events, Visits,
  ReviewLabels, SpeciesSuggestions, exports, analytics truth, media files, model
  artifacts, network calls, or provider runtime calls.
- Future source adapters feed the playback contract instead of redefining the
  Source, Stream, Zone, Event, Visit, review/correction, export, and analytics
  loop.

## Phase 11 — Source adapter boundary

Goal: define the first real Source adapter boundary before adding provider
runtime behavior.

Current work:

- Phase 11A: first real source adapter boundary design.
- Phase 11B: external URL / HTTP still-image provider contract.
- Phase 11C: explicit external URL preview fetch implementation.
- Phase 11D: external URL preview-to-MediaAsset handoff design.
- Phase 11E: explicit preview-to-MediaAsset save implementation.
- Phase 11F: saved preview review/evidence handoff design.
- Phase 11G: explicit saved-preview-to-MotionEvidence creation, no
  Event/Visit/truth.
- Phase 11H: saved preview evidence UI/review polish.
- Phase 11I: external URL media review/promote flow polish.
- Next likely phase: Phase 12A — source/stream smoke-test hardening.

Validation:

- Source adapters remain underneath Sources, Streams, Zones, Events, Visits,
  review/correction, analytics, and exports.
- Provider configuration feeds future adapters without implementing them.
- Source connection status is the product-facing adapter status surface.
- Stream playback status is the product-facing playback surface.
- Recommended first real adapter direction is explicit external URL / HTTP
  still-image preview/status, not a worker.
- Phase 11B defines `external_url` provider fields, explicit preview/status
  behavior, content-type boundaries, SSRF/timeout/security guardrails, storage
  rules, and review/truth boundaries before implementation.
- Phase 11C implements explicit still-image preview fetch with bounded timeout,
  bounded bytes, supported JPEG/PNG/WebP content types, no redirects, no
  workers, no media storage, and no truth creation.
- Phase 11D designs when a transient preview may become a local MediaAsset,
  including provenance, ignored local storage paths, cleanup/retention, Source
  and Stream context, privacy/ignore boundaries, and no automatic truth.
- Phase 11E implements explicit save-as-MediaAsset for external URL previews:
  one bounded still image, existing local media storage, Source/Stream context,
  and no automatic MotionEvidence, Events, Visits, ReviewLabels, or truth.
- Phase 11F designs saved preview MediaAsset -> explicit pending
  MotionEvidence handoff, preserving Source/Stream/Zone context, privacy/ignore
  boundaries, promotion separation, and ReviewLabel correction as truth.
- Phase 11G implements the explicit saved preview MediaAsset -> pending
  MotionEvidence handoff. It requires user action, preserves Source/Stream/Zone
  context where available, stores `snapshot_media_asset_id`, and creates no
  Event, Visit, ReviewLabel, SpeciesSuggestion, DetectionProposal,
  DatasetExport, reviewed status, model output, URL fetch, or media file.
- Phase 11H makes saved-preview-origin MotionEvidence understandable in the
  review UI with attached media preview/file access, safe provenance copy,
  Source/Stream/Zone context, clear status, and explicit ignore/promote actions
  without creating Events, Visits, labels, reviewed status, exports, or truth.
- Phase 11I carries saved-preview context through explicit promotion into
  Event/Visit detail, showing promoted MotionEvidence provenance, saved local
  media context, Source/Stream/Zone context, and correction truth boundaries
  without changing promotion behavior or creating ReviewLabels/export truth.
- Future adapter work does not create MotionEvidence, Events, Visits,
  ReviewLabels, analytics truth, export truth, copied media, model files,
  dependencies, or generated artifacts unless explicitly scoped later.

## Phase 12 — Source/stream validation hardening

Goal: prove the explicit Source/Stream path stays product-shaped before adding
more provider behavior.

Current work:

- Phase 12A: source/stream smoke-test hardening for the explicit external_url
  preview -> MediaAsset -> MotionEvidence -> promotion -> correction path.
- Phase 12B: Source/Stream smoke-test dev checklist for manual browser/API
  validation of the same explicit path.
- Phase 12C: external_url saved media cleanup/retention design.
- Phase 12D: saved media retention report/dry-run API, no deletion.
- Phase 12E: saved media retention UI, dry-run only.
- Phase 12F: low-risk unlinked saved media file cleanup implementation.
- Next likely phase: Phase 13A folder/trail-cam provider boundary design, or
  Phase 12G cleanup UI polish/audit trail design.

Validation:

- Phase 12A adds backend smoke coverage only; it adds no runtime code,
  dependencies, providers, workers, media decoding, automation, model calls, or
  frontend behavior.
- Source setup review, Source connection status, Stream playback status, Event
  detail, Visit detail, and MotionEvidence list/detail do not fetch external
  URLs.
- Explicit preview fetch remains transient and creates no MediaAsset,
  MotionEvidence, Event, Visit, ReviewLabel, SpeciesSuggestion,
  DetectionProposal, DatasetExport, analytics truth, or dataset truth.
- Explicit save creates one local MediaAsset only.
- Explicit saved-media handoff creates one pending MotionEvidence only.
- Explicit promotion creates unreviewed Event/Visit context only.
- ReviewLabel correction remains the first dataset-grade truth write.
- Phase 12B documents the repeatable manual validation path without adding
  backend code, frontend code, tests, dependencies, workers, live playback,
  automatic evidence creation, automatic Event/Visit creation, model runtime, or
  generated artifacts.
- Manual validation must preserve the same truth boundary as Phase 12A: preview
  fetch creates no records, save creates MediaAsset only, media-to-evidence
  creates MotionEvidence only, promote creates Event/Visit only, and correction
  creates ReviewLabel truth.
- Phase 12C designs retention policy only; it adds no delete implementation,
  retention job, API endpoint, UI, backend code, frontend code, tests,
  dependencies, generated media, or truth mutation.
- Phase 12D implements read-only retention reporting and cleanup dry-run
  planning for saved external_url preview MediaAssets. It classifies low,
  medium, high, and protected risk from current MotionEvidence, Event/Visit,
  and ReviewLabel links, reports stale media safely, and deletes no files,
  deletes no records, fetches no URLs, creates no evidence, and mutates no
  truth.
- Phase 12E adds frontend visibility for that retention report and dry-run
  planner. The UI shows risk badges, media state, linkage counts, warnings,
  protected-media skips, and dry-run totals without adding cleanup/delete
  behavior, media deletion, record deletion, evidence creation, or truth
  mutation.
- Phase 12F adds explicit, confirmed, low-risk saved preview file cleanup. It
  deletes only eligible unlinked local files and deletes no MediaAsset records,
  MotionEvidence, Events, Visits, ReviewLabels, DatasetExports, exports,
  analytics truth, classifier truth, or reviewed truth.
- Saved preview cleanup must separate file deletion from MediaAsset record
  deletion, classify risk by linkage/review state, dry-run before destructive
  work, and protect reviewed truth/export/classifier-readiness context by
  default.

## Phase 13 — Folder/trail-cam provider boundary

Goal: define the next local-first Source provider boundary before adding folder
or trail-camera import behavior.

Current work:

- Phase 13A: folder/trail-cam import provider boundary design.
- Phase 13B: folder/trail-cam provider configuration/status contract.
- Phase 13C: folder import preview API, dry-run only.
- Phase 13D: folder import implementation to MediaAssets only.
- Phase 13E: folder import UI preview/import.
- Phase 13F: folder-import-to-MotionEvidence handoff design.
- Phase 13G: single folder-imported MediaAsset to pending MotionEvidence, no
  Event/Visit/truth.
- Phase 13H: batch folder media evidence handoff dry-run/report, no creation.
- Phase 13I: batch folder media evidence creation, pending MotionEvidence only.
- Phase 13J: folder media review/promote UI polish.
- Next likely phase: Phase 14A source/provider consolidation and smoke-test
  expansion.

Validation:

- Phase 13A is docs/design only.
- Phase 13B adds `folder_import_future` to provider definitions, provider
  configuration, Source connection status, Source setup review, and placeholder
  Stream playback only.
- Phase 13C adds `POST /api/sources/{source_id}/folder-import/preview` for
  explicit dry-run preview only.
- Phase 13D adds `POST /api/sources/{source_id}/folder-import` for explicit
  copy-to-local-MediaAsset import only.
- Phase 13E exposes folder preview/import on the Streams page with candidate,
  skipped, warning, and MediaAsset result reporting.
- Phase 13F designs the explicit handoff from folder-imported MediaAssets to
  pending MotionEvidence before any implementation.
- Phase 13G implements that handoff one MediaAsset at a time through explicit
  user action, reusing the shared media evidence route, preserving
  Source/Stream/Zone context, and creating no Event, Visit, ReviewLabel,
  SpeciesSuggestion, DetectionProposal, DatasetExport, analytics/export truth,
  model output, or reviewed truth.
- Phase 13H adds a batch evidence handoff dry-run for already-imported
  folder MediaAssets. It reports eligible, duplicate, skipped, privacy/ignore,
  missing-file, and context-mismatch cases without creating MotionEvidence,
  Event, Visit, ReviewLabel, SpeciesSuggestion, DetectionProposal,
  DatasetExport, analytics/export truth, model output, folder scan, import,
  worker, or reviewed truth.
- Phase 13I adds confirmed batch creation for eligible folder-imported
  MediaAssets. It reuses dry-run eligibility, creates pending MotionEvidence
  only, skips duplicates by default, and creates no Event, Visit, ReviewLabel,
  SpeciesSuggestion, DetectionProposal, DatasetExport, analytics/export truth,
  model output, folder scan, import, worker, promotion, or reviewed truth.
- Phase 13J polishes the review/promote UI for folder-origin evidence. Motion
  Evidence shows folder-imported media, safe provenance, Source/Stream/Zone
  context, and pending/ignored/promoted state; Event/Visit detail can show
  promoted folder-origin media context while correction remains truth.
- Recommended canonical provider key is `folder_import_future`, with display
  name Folder / trail-cam import.
- `folder_path` is required sensitive metadata and must be redacted to
  configured/not-configured in API/UI responses.
- Folder/trail-cam provider work stays underneath Source setup, Source
  connection status, and Stream playback contracts.
- Folder/trail-cam setup represents explicit local batch import readiness, not
  live playback, camera connection, watcher behavior, polling, or background
  indexing.
- Configured folder/trail-cam metadata enables explicit preview planning only;
  Phase 13D adds explicit MediaAsset-only import; it still does not make live
  playback available.
- Preview/import behavior must be explicit, local-first, bounded, and
  review/truth-safe.
- Preview responses return relative candidate/skipped paths only and create no
  MediaAssets, MotionEvidence, Events, Visits, ReviewLabels, DatasetExports,
  SpeciesSuggestions, DetectionProposals, or truth.
- Folder import creates MediaAssets at most by default; MotionEvidence,
  Events/Visits, labels, analytics truth, exports, and classifier readiness
  require explicit future routes and reviewed correction semantics.
  Phase 13G adds the explicit single-media MotionEvidence route, but folder
  import itself still creates MediaAssets only.
- No folder scan, filesystem path validation, media import, media copy/reference
  behavior, media deletion, decoding, worker, scheduler, dependency, generated
  artifact, MediaAsset, MotionEvidence, Event/Visit, ReviewLabel, export, or
  truth creation is added in Phase 13B.
- No import, media copy/reference behavior, media deletion, decoding, worker,
  scheduler, dependency, generated artifact, MediaAsset, MotionEvidence,
  Event/Visit, ReviewLabel, export, or truth creation is added in Phase 13C.
- No MotionEvidence, Event/Visit, ReviewLabel, DatasetExport, SpeciesSuggestion,
  DetectionProposal, analytics truth, export truth, media deletion, decoding,
  worker, scheduler, dependency, generated model/dataset artifact, watcher, or
  polling behavior is added in Phase 13D.
- No MotionEvidence, Event/Visit, ReviewLabel, DatasetExport, SpeciesSuggestion,
  DetectionProposal, analytics truth, export truth, media deletion, decoding,
  worker, scheduler, dependency, generated model/dataset artifact, watcher,
  polling, or live playback behavior is added in Phase 13E.
- No backend code, frontend code, tests, MotionEvidence creation, Event/Visit
  creation, ReviewLabel/truth creation, media deletion, decoding, worker,
  dependency, model/runtime behavior, or generated artifact is added in Phase
  13F.
- No automatic MotionEvidence creation, batch evidence creation, Event/Visit
  creation, ReviewLabel/truth creation, media deletion, decoding, worker,
  dependency, model/runtime behavior, or generated artifact is added in Phase
  13G.
- No MotionEvidence creation, Event/Visit creation, ReviewLabel/truth creation,
  media import/copy/delete, folder scan, decoding, worker, dependency,
  model/runtime behavior, batch creation, or generated artifact is added in
  Phase 13H.
- No automatic MotionEvidence creation, Event/Visit creation, ReviewLabel/truth
  creation, promotion, media import/copy/delete, folder scan, decoding, worker,
  dependency, model/runtime behavior, or generated artifact is added in Phase
  13I.
- No backend behavior, automatic MotionEvidence creation, automatic promotion,
  ReviewLabel/truth creation, folder watcher, polling, media import/copy/delete,
  decoding, worker, dependency, model/runtime behavior, or generated artifact is
  added in Phase 13J.

## Phase 14 — Source/provider flow consolidation

Goal: harden implemented provider paths under one Source/Stream validation
spine before adding another provider or runtime behavior.

Current work:

- Phase 14A: source/provider flow consolidation and smoke-test expansion for
  `external_url` and `folder_import_future`.
- Phase 14B: source/provider dashboard/status polish for read-only provider
  workflow readiness and next-action cues.
- Phase 14C: next provider boundary decision after `external_url` and
  `folder_import_future`.
- Phase 14D: generic webhook ingest provider boundary design.
- Phase 14E: webhook provider configuration/status contract.
- Phase 14F: webhook payload validation/dry-run endpoint, no records.
- Phase 14G: webhook metadata event to pending MotionEvidence, explicit/evidence
  only.
- Phase 14H: webhook provider smoke-test hardening through correction truth.
- Phase 14I: webhook review/promote UI provenance polish.
- Follow-on phase: Phase 15A MVP source/provider readiness consolidation.

Validation:

- Phase 14A adds consolidated backend smoke coverage for both implemented
  provider paths.
- `external_url` is validated from provider configuration through explicit
  preview, explicit MediaAsset save, explicit pending MotionEvidence handoff,
  explicit promotion, and explicit ReviewLabel correction.
- `folder_import_future` is validated from provider configuration through
  explicit folder preview, explicit MediaAsset import, explicit single and batch
  pending MotionEvidence handoff, explicit promotion, and explicit ReviewLabel
  correction.
- Source setup review, Source connection status, and Stream playback status are
  read-only and must not fetch URLs, scan folders, create media, create
  evidence, or claim live playback.
- Dashboard/source overview may summarize provider readiness and route users to
  explicit Streams, Motion Evidence, Retention, and Review workflows, but it
  must not run providers, create media/evidence, or create truth.
- Phase 14C recommends generic webhook ingest as the next provider boundary to
  design before implementation, with HTTP/MJPEG design as the alternate visual
  source-expansion path.
- Future webhook work must keep incoming media/events/detections as
  MediaAsset/MotionEvidence/proposal evidence until user review/correction.
- Phase 14D defines the generic webhook ingest boundary: `webhook_future`,
  metadata-only setup, future authenticated validation, future MediaAsset or
  MotionEvidence mapping only when explicitly scoped, and no reviewed truth.
- Phase 14E represents Generic webhook ingest in provider definitions, redacted
  configuration, Source connection status, setup review, and placeholder Stream
  playback. Missing shared-secret metadata stays `not_configured`; configured
  metadata stays future-adapter-required because no endpoint accepts payloads.
- Phase 14F adds explicit webhook payload validation/dry-run at
  `POST /api/sources/{source_id}/webhook/validate`. It validates generic payload
  shape and Source/Stream/Zone context, reports candidate mappings, rejects
  privacy/ignore-zone candidates, and creates no records or truth.
- Phase 14G adds explicit webhook metadata motion evidence creation at
  `POST /api/sources/{source_id}/webhook/motion-evidence`. It requires
  confirmation, accepts motion payloads only, creates pending MotionEvidence
  only, skips duplicate `external_event_id` values by default, and creates no
  MediaAssets, Events/Visits, labels, or truth.
- Phase 14H adds backend smoke coverage for the complete metadata webhook path:
  setup/status and Stream playback stay read-only, validation dry-run creates
  nothing, explicit webhook motion ingest creates pending MotionEvidence only,
  explicit promotion creates Event/Visit context only, and correction creates
  ReviewLabel truth.
- Phase 14I surfaces webhook-origin MotionEvidence provenance in the frontend:
  provider key, external event ID, untrusted label/confidence, and timestamp can
  appear in Motion Evidence, Event Detail, and Visit Detail as evidence metadata
  only. Promotion and correction behavior stay explicit.
- MediaAssets remain media context, MotionEvidence remains evidence, and
  Event/Visit promotion remains unreviewed until correction.
- No frontend feature, new provider, live playback, folder watcher, polling,
  worker, media decoding, model runtime, dependency, automatic evidence, or
  generated artifact is added in Phase 14A.
- No new provider behavior, live playback, folder watcher, polling, worker,
  media decoding, model runtime, dependency, automatic evidence, truth write, or
  generated artifact is added in Phase 14B.
- No backend code, frontend code, tests, endpoint, database model, provider
  implementation, dependency, live playback, worker, polling, media decoding,
  automatic evidence, truth write, or generated artifact is added in Phase 14C.
- No backend code, frontend code, tests, endpoint, webhook ingest, auth/token
  code, media upload, media download, MediaAsset creation, MotionEvidence
  creation, Event/Visit creation, ReviewLabel/truth creation,
  ecosystem-specific integration, MQTT, worker, queue, polling, dependency,
  model/runtime behavior, or generated artifact is added in Phase 14D.
- No webhook ingest endpoint, auth/token generation, payload parsing, media
  upload/download behavior, MediaAsset creation, MotionEvidence creation,
  Event/Visit creation, ReviewLabel/truth creation, ecosystem-specific
  integration, MQTT, worker, queue, polling, dependency, model/runtime behavior,
  live playback, or generated artifact is added in Phase 14E.
- No webhook ingest, real auth/token generation, media upload/download,
  MediaAsset creation, MotionEvidence creation, Event/Visit creation,
  ReviewLabel/truth creation, ecosystem-specific integration, MQTT, worker,
  queue, polling, dependency, model/runtime behavior, live playback, external
  network call, or generated artifact is added in Phase 14F.
- No general webhook ingest, real auth/token generation, media upload/download,
  MediaAsset creation, Event/Visit creation, ReviewLabel/truth creation,
  SpeciesSuggestion creation, DetectionProposal creation, ecosystem-specific
  integration, MQTT, worker, queue, polling, dependency, model/runtime behavior,
  live playback, external network call, or generated artifact is added in Phase
  14G.
- No frontend feature, backend behavior change, general webhook ingest, real
  auth/token generation, media upload/download, MediaAsset creation,
  SpeciesSuggestion creation, DetectionProposal creation, ecosystem-specific
  integration, MQTT, worker, queue, polling, dependency, model/runtime behavior,
  live playback, external network call, or generated artifact is added in Phase
  14H. Event/Visit and ReviewLabel changes appear only through existing promote
  and correction routes under smoke test.
- No webhook media upload/download, automatic promotion, automatic labels,
  ReviewLabel/truth creation, ecosystem-specific integration, worker, queue,
  polling, dependency, model/runtime behavior, live playback, external network
  call, or generated artifact is added in Phase 14I.

## Phase 15 — MVP readiness and onboarding consolidation

Goal: make the current stream/source MVP understandable without adding provider
runtime behavior.

Current work:

- Phase 15A: MVP source/provider readiness consolidation.
- Phase 15B: MVP demo script/checklist.
- Phase 15C: onboarding and empty-state polish.
- Phase 15D: local MVP release/readiness checklist.
- Phase 15E: UI copy reduction pass.
- Follow-on phase: Phase 16A worker/lifecycle boundary design.

Design note: [mvp-readiness-consolidation.md](mvp-readiness-consolidation.md).
Demo script: [mvp-demo-script.md](mvp-demo-script.md).
Onboarding/empty states:
[onboarding-empty-state-polish.md](onboarding-empty-state-polish.md).
Local MVP readiness checklist:
[local-mvp-readiness-checklist.md](local-mvp-readiness-checklist.md).

Validation:

- Dashboard/source overview explains current provider workflow readiness,
  explicit next actions, review/evidence status, correction truth, and
  export/classifier readiness without claiming live playback.
- `external_url` is presented as explicit preview -> MediaAsset -> pending
  MotionEvidence -> explicit promotion -> correction truth.
- `folder_import_future` is presented as explicit folder preview/import ->
  MediaAsset -> pending MotionEvidence -> explicit promotion -> correction
  truth.
- `webhook_future` is presented as API validation/metadata motion evidence ->
  pending MotionEvidence -> explicit promotion -> correction truth, with UI
  ingest controls still future.
- `manual_media` is presented as explicit local import -> review/correction
  truth.
- Readiness/dashboard surfaces remain read-only and do not fetch URLs, scan
  folders, process webhook payloads, create MediaAssets, create MotionEvidence,
  create Events/Visits, create ReviewLabels, run models, or generate artifacts.
- Media and evidence are not truth; reviewed corrections remain the source for
  analytics, exports, and classifier readiness.
- No new provider behavior, new backend endpoint, live playback, media decoding,
  dependency, model runtime, training behavior, automatic evidence, automatic
  Event/Visit creation, automatic truth creation, or generated artifact is
  added in Phase 15A.
- Phase 15B provides one repeatable local walkthrough for the current MVP spine:
  fresh local app, provider readiness, explicit provider actions,
  MotionEvidence review/promote, correction truth, analytics/export/classifier
  readiness, saved media retention, and artifact safety.
- Phase 15B is documentation only. It adds no backend code, frontend code,
  tests, endpoints, database models, scripts, generated media, seed assets,
  dependencies, provider behavior, live playback, workers, polling, watchers,
  automation, model runtime, training behavior, or generated artifacts.
- Phase 15C makes sparse/fresh local app states explain the product path:
  Source setup, explicit provider action, MediaAsset/MotionEvidence evidence,
  promotion, Visit correction, and analytics/export/classifier readiness.
- Phase 15C frontend surfaces remain read-only guidance. They do not fetch
  provider media, scan folders, process webhook payloads, create MediaAssets,
  create MotionEvidence, create Events/Visits, create ReviewLabels, run models,
  or generate artifacts.
- Phase 15D should turn the current MVP spine into a local release/readiness
  checklist after onboarding copy, demo flow, and validation expectations are
  clean.
- Phase 15D is documentation/checklist only. It defines local demo/dev
  readiness, known limitations, validation commands, provider smoke-test gates,
  artifact safety, and the truth boundary without adding runtime behavior.
- Local MVP demo-ready means the required validation passes and
  [mvp-demo-script.md](mvp-demo-script.md) can be completed. It is not a
  public/product release claim.
- Follow-on work should come from known gaps: reduce UI copy if it feels heavy,
  design worker/lifecycle boundaries before background behavior, design
  live/source automation before source automation, and select live provider work
  through an explicit decision phase.
- Phase 15E reduces repetitive explanatory UI copy from Phase 15C while keeping
  concise next actions, truth-boundary cues, cleanup warnings, and detailed
  guardrails in docs.
- Phase 15E adds no behavior, provider work, backend/frontend data contract,
  tests, dependencies, generated artifacts, or release claim.

## Phase 16 — Worker and lifecycle boundaries

Goal: define optional worker lifecycle rules before any background behavior is
added.

Current work:

- Phase 16A: worker/lifecycle boundary design.
- Phase 16B: worker status schema/API contract, read-only/no workers.
- Phase 16C: worker status UI, read-only/no workers.
- Phase 16D: disabled no-op worker registry/status contract.
- Phase 16E: external_url worker dry-run plan API.
- Phase 16F: Worker Status UI dry-run plan integration.
- Next likely phase: Phase 16G folder import worker dry-run plan API.

Design note: [worker-lifecycle-boundary-design.md](worker-lifecycle-boundary-design.md).

Validation:

- Phase 16A keeps provider flows explicit and documents future automation
  candidates without implementing workers, schedulers, polling, watchers,
  queues, provider behavior, media writes, evidence creation, Event/Visit
  creation, label/truth creation, dependencies, or generated artifacts.
- Workers are optional, local-first, disabled by default initially, observable,
  bounded, and safely stoppable.
- Worker status is lifecycle metadata only and must not create evidence or
  truth.
- Future worker output can become pending MotionEvidence, DetectionProposal, or
  SpeciesSuggestion at most; ReviewLabel correction remains truth.
- Privacy and ignore zones must block or skip automated evidence creation.
- Storage estimates and retention rules are required before repeated
  fetch/import/generation behavior.
- Follow-on implementation must start with read-only status contracts before any
  active background work.
- Phase 16B adds `GET /api/workers/status` as a read-only future worker
  visibility contract. It returns disabled, unimplemented placeholder workers
  with all create/truth flags false and no provider execution.
- Phase 16B adds backend schema/API/tests only. It adds no frontend, worker
  runtime, scheduler, polling, watcher, queue, background job, provider
  execution, external URL fetch, folder scan, webhook processing, MediaAsset,
  MotionEvidence, Event/Visit, ReviewLabel/truth, model runtime, dependency, or
  generated artifact.
- Phase 16C adds a frontend Worker Status page and Dashboard link over the
  read-only status route. It adds no backend behavior, worker runtime,
  scheduler, polling, watcher, queue, background job, provider execution, media
  creation, evidence creation, Event/Visit, ReviewLabel/truth, dependency, or
  generated artifact.
- Phase 16D moves future worker placeholders into a metadata-only registry so
  future automation has one disabled status attachment point. It adds no
  callbacks, start/run/enable methods, scheduling config, worker runtime,
  scheduler, polling, watcher, queue, background job, provider execution, media
  creation, evidence creation, Event/Visit, ReviewLabel/truth, dependency, or
  generated artifact.
- Phase 16E adds `GET /api/workers/external-url-preview/dry-run` as an explicit
  planning route over local Source/provider configuration. It considers
  `external_url` Sources only and keeps every would-fetch/create/truth flag
  false. It adds no worker runtime, scheduler, polling, background job, HTTP
  request, provider execution, media creation, evidence creation, Event/Visit,
  ReviewLabel/truth, dependency, or generated artifact.
- Phase 16F exposes the external_url dry-run plan in Worker Status UI. It adds
  no worker runtime, scheduler, polling, background job, provider execution,
  fetch, media creation, evidence creation, Event/Visit, ReviewLabel/truth,
  dependency, or generated artifact.

## Phase 17 — Evidence review efficiency

Goal: make explicit evidence review faster while preserving the correction truth
boundary.

Deliverables:

- Phase 17A: bulk MotionEvidence review actions.
- Phase 17B: bulk saved media to MotionEvidence triage.
- Phase 17C: bulk Review Queue correction actions.
- Phase 17D: Review Queue filters and bulk selection safety.
- Phase 17E: Review correction label helpers.
- Phase 17F: Review correction label validation.
- Phase 17G: Review correction history and latest-truth visibility.
- Phase 17H: Promotion result links and evidence traceability.
- Phase 17I: MotionEvidence detail route and trace links.
- Phase 17J: MotionEvidence detail actions.
- Next likely phase: Phase 17K source/stream smoke-test validation polish.

Validation:

- Phase 17A adds pending-only bulk ignore/promote actions for MotionEvidence.
  Bulk ignore creates no Event, Visit, ReviewLabel, export, analytics, or truth.
  Bulk promote reuses explicit promotion semantics to create reviewable
  Event/Visit context only; corrections remain the first dataset/export truth.
  It adds no workers, scheduler, provider changes, media import/fetch/scan
  changes, model runtime, dependencies, or generated artifacts.
- Phase 17B lets users select multiple eligible saved MediaAssets and create
  pending MotionEvidence in bulk. It creates no Event, Visit, ReviewLabel,
  reviewed truth, analytics/export truth, media import/fetch/scan behavior,
  worker, scheduler, dependency, or generated artifact.
- Phase 17C lets users select multiple eligible Review Queue items and apply
  the same explicit correction in bulk. It creates ReviewLabels as user-selected
  truth only, with no automatic labels, MediaAssets, MotionEvidence, new
  Events/Visits, model runtime, worker, scheduler, provider change, dependency,
  or generated artifact.
- Phase 17D lets users narrow the Review Queue with client-side search, target,
  and review-status filters before selecting visible eligible unreviewed items.
  Filter changes clear selection and previous bulk result summaries. It adds no
  backend filters, automatic labels, new truth path, worker, provider behavior,
  dependency, or generated artifact.
- Phase 17E adds compact label helper chips in the Review Queue from existing
  taxonomy labels, recent ReviewLabels, and current suggested labels. Helpers
  fill correction fields only; explicit single or bulk correction submit remains
  required before ReviewLabel truth exists.
- Phase 17F shows compact validation feedback for Review Queue correction
  labels, distinguishing suggested, recent, taxonomy, and custom labels without
  blocking custom local labels or creating truth before explicit submit.
- Phase 17G makes latest ReviewLabel correction truth and compact correction
  history visible in Review Queue audit context plus Event and Visit detail
  pages, using existing read-only correction data without changing truth
  creation.
- Phase 17H adds direct Event/Visit links from single and bulk MotionEvidence
  promotion results, shows promoted target links on promoted evidence, and makes
  source MotionEvidence/media traceability visible on Event and Visit detail
  pages without changing promotion or correction truth semantics.
- Phase 17I adds a focused read-only MotionEvidence detail view using the
  existing detail API and links to it from promote results, promoted evidence
  rows, Event Detail, and Visit Detail. It changes no backend behavior,
  promotion semantics, correction semantics, or truth creation path.
- Phase 17J lets pending MotionEvidence be promoted or ignored directly from
  the detail view using the existing single-action APIs. Promote still creates
  reviewable Event/Visit context only, ignore creates no review records, and
  ReviewLabel correction remains the first dataset/export truth path.

## Phase 18 — Classifier readiness drill-down

Goal: make classifier readiness auditable from reviewed correction examples
without adding training or model runtime behavior.

Deliverables:

- Phase 18A: classifier readiness drill-down examples.
- Next likely phase: Phase 18B classifier readiness gap action polish.

Validation:

- Phase 18A lets users select a readiness label/species and inspect matching
  ReviewLabel examples with Event/Visit detail links where target ids allow.
  It uses existing read-only ReviewLabel data, creates no ReviewLabels, runs no
  training/model code, changes no export format, and preserves correction as
  classifier truth.
