# Codex Guardrails

MockingBird is a local-first outdoor video intelligence platform. Video streams are central.

Before implementation work, Codex must read:

- [README.md](README.md)
- [docs/product-doctrine.md](docs/product-doctrine.md)
- [docs/roadmap.md](docs/roadmap.md)
- [docs/glossary.md](docs/glossary.md)
- [docs/architecture.md](docs/architecture.md)

## Core Doctrine

Users connect outdoor camera/video sources, view streams in the app, draw zones, MockingBird analyzes video for animals/outdoor events, creates reviewable visits/events, users correct labels/species, and corrections build dataset exports and analytics over time.

Core product loop:

connect source → view stream → draw zones → analyze outdoor activity → review visits/events → correct labels/species → export datasets and analytics.

Preserve these product concepts:

- Source
- Stream
- Zone
- Event
- Visit
- Detection
- Review/correction
- Dataset export
- Analytics

Source adapters are underneath the product. They normalize media and activity into product-level concepts instead of defining the product.

## Product Drift To Avoid

Do not center MockingBird on:

- Windows USB
- PowerShell
- CLI tools
- ROI wording
- interval analysis
- debug internals
- snapshot loops
- a single camera adapter
- hardware setup as the main product

## Task Packet

Every future implementation task must restate:

- roadmap phase
- product flow improved
- why this is next
- files allowed
- non-goals
- validation tier

## Architecture Guidance

- Build the product model first, adapters later.
- Build stream-first UX assumptions into the API/frontend.
- Treat detections as evidence, not final truth.
- Treat user corrections as dataset-grade labels.
- Before adding real model dependencies or detector behavior, read
  [docs/model-adapter-guardrails.md](docs/model-adapter-guardrails.md) and
  [docs/model-selection.md](docs/model-selection.md). Model outputs must remain
  `DetectionProposal` evidence until user review/correction.
- MegaDetector-family integrations must remain evidence-only adapters and must
  not bypass Review Queue or Visit Detail correction.
- Real MegaDetector runtime work must follow
  [docs/megadetector-runtime-plan.md](docs/megadetector-runtime-plan.md) and stay
  optional, lazy-loaded, local, and evidence-only.
- Species/classifier outputs must follow
  [docs/species-suggestion-adapter-design.md](docs/species-suggestion-adapter-design.md)
  and remain suggestion evidence only until explicit review/correction creates
  truth.
- SpeciesNet or classifier runtime work must follow
  [docs/speciesnet-runtime-investigation.md](docs/speciesnet-runtime-investigation.md),
  [docs/speciesnet-source-review.md](docs/speciesnet-source-review.md), and
  [docs/speciesnet-adapter-boundary-plan.md](docs/speciesnet-adapter-boundary-plan.md).
  It must not add dependencies, model files, automatic downloads, or classifier
  calls without explicit scope that preserves the optional adapter boundary.
- Custom classifier or training work must follow
  [docs/custom-bird-classifier-dataset-plan.md](docs/custom-bird-classifier-dataset-plan.md)
  and
  [docs/classifier-training-manifest-design.md](docs/classifier-training-manifest-design.md)
  and must not add training dependencies, model files, generated datasets, or
  runtime behavior without explicit scope. Reviewed corrections remain training
  truth; suggestions remain evidence.
- Generated classifier dataset/export files require explicit export scope,
  must follow
  [docs/classifier-manifest-file-export-design.md](docs/classifier-manifest-file-export-design.md),
  must remain under ignored local data/export paths, and must not be committed.
- Copied classifier media bundles or generated datasets require explicit scope,
  must follow
  [docs/media-copy-export-design.md](docs/media-copy-export-design.md),
  must remain under ignored local data/export paths, must not be committed, and
  must not create reviewed truth.
- External classifier training work must follow
  [docs/external-training-workflow.md](docs/external-training-workflow.md) and
  [docs/external-training-workspace-checklist.md](docs/external-training-workspace-checklist.md);
  training dependencies, generated datasets, model artifacts, and checkpoints
  require explicit scope and ignored local paths.
- Workspace templates/docs must not create real folders, generated datasets,
  model artifacts, dependencies, or training scripts without explicit scope.
- Stream/source playback work must follow
  [docs/stream-source-playback-contract.md](docs/stream-source-playback-contract.md).
  Playback status is product-level, read-only, and must not create evidence,
  reviewed truth, exports, analytics truth, capture behavior, or adapter runtime
  work unless explicitly scoped.
- Source connection/provider work must follow
  [docs/source-connection-provider-contract.md](docs/source-connection-provider-contract.md)
  and stay product-level until real provider implementation is explicitly scoped.
- Source provider configuration work must follow
  [docs/source-provider-configuration-contract.md](docs/source-provider-configuration-contract.md).
  Configuration is metadata-only and must not connect to sources, validate URLs,
  store raw secrets, capture frames, decode media, or create product truth.
- Real source adapter implementation must follow
  [docs/source-adapter-boundary-design.md](docs/source-adapter-boundary-design.md)
  and explicit task scope. Do not add capture, decoding, workers, network calls,
  dependencies, generated media, or truth creation by accident.
- External URL provider implementation must follow
  [docs/external-url-still-image-provider-contract.md](docs/external-url-still-image-provider-contract.md)
  and explicit phase scope. Do not add URL fetches without SSRF, timeout,
  content-type, secret-redaction, storage, and truth-boundary guardrails.
  External URL fetches must remain explicit, bounded, no-worker, and no-truth
  unless a later task scopes a different lifecycle.
- Saving fetched previews as MediaAssets must follow
  [docs/external-url-preview-media-asset-handoff-design.md](docs/external-url-preview-media-asset-handoff-design.md),
  use ignored local paths, require explicit scope, and create no truth by itself.
- Saved preview MediaAssets must follow
  [docs/saved-preview-review-evidence-handoff-design.md](docs/saved-preview-review-evidence-handoff-design.md)
  before becoming evidence, Events, Visits, labels, analytics truth, export truth,
  or classifier truth.
- Source setup review/status work must remain read-only and must not connect to
  sources, capture/decode media, run adapters/models, or create evidence/truth.
- Local MegaDetector setup must follow
  [docs/megadetector-local-setup.md](docs/megadetector-local-setup.md), and model
  artifacts must never be committed.
- PyTorch-Wildlife/MegaDetector runtime work is experimental unless a future task
  explicitly reopens it after
  [docs/megadetector-runtime-findings.md](docs/megadetector-runtime-findings.md).
  Do not add heavy detector runtimes, model files, or download behavior without
  that checkpoint.
- The current active event trigger direction is zone-aware motion trigger; see
  [docs/stream-motion-trigger-plan.md](docs/stream-motion-trigger-plan.md).
- Keep local-first storage/export assumptions in mind.
- Respect privacy and ignore zones as first-class product concepts when those features are implemented.
- Avoid adapter-specific models leaking into core product models.

## Comment Standard

When implementation code is added later, include clear comments where they help future maintainers understand product intent, domain meaning, non-obvious constraints, or decisions that prevent product drift.

Good comments explain:

- product intent
- domain meaning
- why a model, endpoint, or workflow exists
- non-obvious constraints
- decisions that prevent product drift
- validation assumptions

Avoid comments that merely repeat obvious syntax.

Useful future comment examples:

- Source adapters normalize into Streams/Events rather than defining the product.
- Detection is model evidence, not user-confirmed truth.
- ReviewLabel or equivalent correction models represent dataset-grade user truth.
- Privacy and Ignore zones affect event creation/review behavior.
- Demo data exists to prove the product flow before real camera adapters.

## Validation Expectations

- Prefer tests for implementation work.
- For docs-only changes, validate by checking scope, file list, and product language.
- Every task report should include changed files, validation performed, and deviations from scope.
