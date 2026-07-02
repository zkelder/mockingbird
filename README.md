# MockingBird

MockingBird is a local-first outdoor video intelligence platform.

Video streams are central to the product. Users connect outdoor camera and video sources, view streams in the app, draw zones on those streams, and let MockingBird analyze outdoor activity over time.

The first vertical is backyard bird feeder monitoring and species review. The broader product direction is outdoor video intelligence for wildlife, yard activity, pets, cats, squirrels, people, vehicles, feeders, birdbaths, and meaningful outdoor observations.

## Core product loop

1. Connect an outdoor camera or video source.
2. View the live stream in MockingBird.
3. Draw zones on the stream, such as feeder, birdbath, ground, driveway, privacy, or ignore zones.
4. MockingBird analyzes video for animals and outdoor activity.
5. The app creates reviewable visits and events.
6. Users correct species, labels, zones, and event meaning.
7. Corrections build local datasets, exports, and analytics over time.

## Product principles

- Local-first by default.
- Streams are the center of the experience.
- Zones make video understandable.
- Events and visits are reviewable, not blindly trusted.
- User corrections improve the local dataset.
- Source adapters are underneath the product, not the product center.
- Bird feeder species review is the first vertical, not the final product boundary.

## Development workflow

Codex and contributor guidance lives in [AGENTS.md](AGENTS.md). The scoped task workflow lives in [docs/development-workflow.md](docs/development-workflow.md).

## Local development

Create a virtual environment, install the API with test dependencies, and run the local contract tests:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
python -m pytest
```

Run the product API locally:

```sh
python -m uvicorn mockingbird.api.main:app --reload
```

Then open http://127.0.0.1:8000/docs.

The API contract includes list routes, detail routes, nested source/stream/event routes, a review queue, dataset exports, and an analytics summary.

Stream Detail also reads a product-level playback status contract. Current streams
can show demo or placeholder panels while future source adapters feed real
playback without changing zone editing or review/correction truth. See
[docs/stream-source-playback-contract.md](docs/stream-source-playback-contract.md).

Sources also expose a read-only connection/provider status contract for demo,
not-configured, unavailable, offline, or future-provider-ready states. See
[docs/source-connection-provider-contract.md](docs/source-connection-provider-contract.md).

Source setup can store provider configuration metadata only, with secret fields
redacted to configured/not-configured markers. See
[docs/source-provider-configuration-contract.md](docs/source-provider-configuration-contract.md).
The Streams page also shows a read-only Source setup review that combines setup
metadata, connection readiness, and Stream playback readiness without connecting
to sources or creating product truth.
The frontend presents that Source setup, Stream playback status, Zone editing,
and manual import path as one stream-first workflow.
For `manual_media` Sources, that review points to the existing Import Media flow:
explicit imports can create reviewable Events/Visits, while corrections remain
the source of truth.

The first real Source adapter boundary is design-only and documented in
[docs/source-adapter-boundary-design.md](docs/source-adapter-boundary-design.md).
The recommended next direction is an explicit external URL / HTTP still-image
preview/status path that feeds existing Source connection and Stream playback
contracts without workers or truth creation.
The provider-specific contract is documented in
[docs/external-url-still-image-provider-contract.md](docs/external-url-still-image-provider-contract.md);
it defines required metadata, explicit preview/status behavior, security
guardrails, storage limits, and review/truth boundaries before implementation.
The current implementation can fetch an explicit still-image preview for
configured `external_url` Sources. It is transient, not saved, not live playback,
and creates no Events/Visits or truth.
The current implementation can also save that fetched preview as one local
MediaAsset through an explicit user action. It creates no Events, Visits,
MotionEvidence, ReviewLabels, or truth. The boundary is documented in
[docs/external-url-preview-media-asset-handoff-design.md](docs/external-url-preview-media-asset-handoff-design.md);
saving fetched previews must be explicit, local, bounded, and truth-safe.
Saved previews can now enter review as pending MotionEvidence through an
explicit user action documented in
[docs/saved-preview-review-evidence-handoff-design.md](docs/saved-preview-review-evidence-handoff-design.md);
saved preview media still cannot create Events, Visits, labels, or truth without
explicit promotion and later review/correction.

Local product metadata and review state persist to `data/mockingbird.sqlite3` by default. Set `MOCKINGBIRD_DB_URL` to use another database URL for development or tests. Manual and folder imports store local media files under `data/media/imports/` by default; set `MOCKINGBIRD_MEDIA_ROOT` to use another local media root. The `data/` directory is ignored. Imported media is not analyzed, transcoded, or copied into exports in this phase. The Local Data page shows database status and can reset seeded demo metadata.

## Local frontend development

Run the backend API:

```sh
python -m uvicorn mockingbird.api.main:app --reload
```

Run the stream-first frontend:

```sh
cd web
npm install
npm run dev
```

The frontend defaults to http://127.0.0.1:8000 for the API. Set `VITE_API_BASE_URL` to point at a different local API.

## Local detector spike

The Local Image Detector adapter is optional, evidence-only, and disabled until configured with a local model file. No model files are committed or downloaded automatically.

```sh
export MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH=/path/to/local-detector.onnx
export MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH=/path/to/labels.txt # optional
```

Detector outputs create detection proposals only. Users still convert, review, and correct proposals before exports or analytics treat labels as truth.

MegaDetector remains a useful future detector/proposal family. The current wrapper is unavailable-safe, bundles no model files, downloads nothing, and expects a future local `MOCKINGBIRD_MEGADETECTOR_MODEL_PATH` configuration before real runs.

The PyTorch-Wildlife/MegaDetector runtime path is archived as experimental pending dependency, license, and download-behavior review. See [docs/megadetector-runtime-findings.md](docs/megadetector-runtime-findings.md).

The current active implementation path is stream/zones/motion-trigger/snapshot evidence/species-suggestion/review truth. See [docs/stream-motion-trigger-plan.md](docs/stream-motion-trigger-plan.md).

Motion Evidence is the bridge from motion candidates to later reviewable visits/events; see [docs/motion-evidence-design.md](docs/motion-evidence-design.md).

Motion Evidence has manual creation, review, and promotion surfaces for exercising unreviewed Event/Visit evidence; see [docs/motion-evidence-design.md](docs/motion-evidence-design.md) and [docs/motion-evidence-promotion-design.md](docs/motion-evidence-promotion-design.md).

The motion API can also evaluate caller-provided frame sequences and optionally create pending Motion Evidence without creating review truth.

Sampled-frame ingestion is the planned bridge from visible streams to frame-plane motion evaluation; see [docs/sampled-frame-ingestion-design.md](docs/sampled-frame-ingestion-design.md).

The Motion Evidence page includes a sampled-frame evaluation harness for supplied tiny frame planes; it can create pending evidence only.

The backend sampler abstraction now evaluates supplied in-memory frame planes; see [docs/lightweight-sampler-abstraction.md](docs/lightweight-sampler-abstraction.md).

Best-frame media attachment remains optional evidence context; its schema/API compatibility path is documented in [docs/best-frame-media-attachment-design.md](docs/best-frame-media-attachment-design.md).

Local frame artifacts are a design-only bridge from best-frame indexes to future local visual evidence; see [docs/local-frame-artifact-design.md](docs/local-frame-artifact-design.md).

Pending Motion Evidence can attach an existing local MediaAsset as visual evidence without creating labels, reviewed observations, or export-ready truth.

Manual pending Motion Evidence creation can also start with an existing MediaAsset attached.

The Motion Evidence page shows attached MediaAsset context through the existing media preview/file route.

The current local demo loop is import media -> create media-backed Motion Evidence -> promote -> review/correct.

Species suggestion now has a manual/mock evidence surface and a frontend prefill path into Visit correction: suggestions are evidence only until review/correction creates truth, and accepted status after correction is evidence metadata only. See [docs/species-suggestion-adapter-design.md](docs/species-suggestion-adapter-design.md) and [docs/species-suggestion-correction-flow.md](docs/species-suggestion-correction-flow.md).

Visit review UI keeps species suggestions near correction while preserving the correction form as the reviewed truth action.

Reviewed media-backed bird visits can feed the classifier manifest preview and metadata-only backend file export, but only reviewed corrections count as training truth. The frontend can dry-run and create local manifest metadata exports under an ignored export path; the backend can also dry-run future copy-media planning without copying media. MockingBird still does not copy media, train, or run classifier runtime. See [docs/external-training-workspace-template.md](docs/external-training-workspace-template.md), [docs/external-training-workspace-checklist.md](docs/external-training-workspace-checklist.md), [docs/media-copy-export-design.md](docs/media-copy-export-design.md), [docs/external-training-workflow.md](docs/external-training-workflow.md), [docs/classifier-manifest-file-export-design.md](docs/classifier-manifest-file-export-design.md), [docs/custom-bird-classifier-dataset-plan.md](docs/custom-bird-classifier-dataset-plan.md), and [docs/classifier-training-manifest-design.md](docs/classifier-training-manifest-design.md).

SpeciesNet is under docs-only runtime/source review as a future optional suggestion adapter, with a boundary plan before any runtime work. See [docs/speciesnet-runtime-investigation.md](docs/speciesnet-runtime-investigation.md), [docs/speciesnet-source-review.md](docs/speciesnet-source-review.md), and [docs/speciesnet-adapter-boundary-plan.md](docs/speciesnet-adapter-boundary-plan.md).

Before wiring a real detector model, follow [docs/model-adapter-guardrails.md](docs/model-adapter-guardrails.md), [docs/model-selection.md](docs/model-selection.md), the [MegaDetector decision record](docs/detector-decision-megadetector.md), the [MegaDetector runtime plan](docs/megadetector-runtime-plan.md), and the [local setup checklist](docs/megadetector-local-setup.md).

## Not the product center

MockingBird is not centered on Windows USB camera scripts, PowerShell, CLI tools, interval analysis, snapshot loops, ROI language, or debug internals.

Those may exist as implementation details or developer utilities later, but they are not the product.
