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
In the browser, the product path is: select an external snapshot camera/source,
Test snapshot, Capture snapshot, Analyze image, Review/correct, then Export
reviewed data.
The Streams page now also supports a first Live view path for browser-playable
stream URLs configured on an `external_url` Source. MJPEG uses a browser image
stream; browser video and direct browser-supported HLS use the native video
element without a new dependency. RTSP URLs can use the optional local bridge
when system `ffmpeg` is installed on the MockingBird host. That bridge starts
only for the active Live view request, returns MJPEG to the browser, stores no
media, and creates no review truth or exports.
MockingBird also has a first local USB/webcam Live view path through the
`local_usb` provider. Linux `/dev/video0`-style devices are the first supported
target, using optional system `ffmpeg` only while the browser Live view is open.
If `ffmpeg` or the device path is unavailable, the app reports that local camera
playback is unavailable without affecting setup, review, export, or monitoring.
Windows webcams can use the same `local_usb` provider with `windows_dshow` and
an optional Windows `ffmpeg.exe` DirectShow bridge. If the API runs in WSL,
configure a Windows ffmpeg path such as `/mnt/c/ffmpeg/bin/ffmpeg.exe`; WSL USB
passthrough is not the recommended webcam path. This Live view starts ffmpeg
only for the active request and creates no media, truth, or exports.
The Streams page shows Source health / Camera status for each selected Stream so
manual checks can confirm the last snapshot test, last capture, saved image
count, and motion readiness. Camera Monitoring Core can now start and stop an
explicit backend-managed in-memory monitor for an `external_url` Stream. It uses
existing still-image snapshot capture, saved-media motion checks, source health,
and storage guardrails. It does not survive API restart and creates no automatic
truth or exports.
When monitoring detects user-zone-backed activity, the Streams page can offer an
explicit `Create review activity` handoff to pending review activity. Automatic
activity areas remain result-only until a named Zone is available, and
correction/export truth stays user-confirmed.
Users can explicitly mark a useful automatic activity area as a named Zone such
as feeder, birdbath, ground, yard, driveway, ignore, or privacy. That creates a
real stream Zone from the activity bounds so future checks can use the normal
Zone-backed review path. Privacy and ignore Zones suppress future activity in
those areas; no fake Zones, review truth, or exports are created automatically.
Field test readiness on Cameras/Streams summarizes the real-camera validation
path for a selected Stream: configure/select an `external_url` source, Test
snapshot, Capture two snapshots, Check motion, mark an activity area as a Zone
when needed, Start monitoring, create review activity, correct it, confirm Bird
Log, and Export reviewed data.
The same Stream cards now show Storage guardrails: saved image counts, storage
warnings, and reviewed/export-linked media protection before and during
monitoring. Snapshot watch remains an advanced bounded page-local test harness.
This adds no deletion, cleanup, bundled media runtime, Pi/cellular behavior,
model runtime, automatic truth, or automatic export behavior.
Reviewed and needs-review observations are visible in the Bird Log, which turns
captured or imported activity into a user-facing local history before export.
Saved previews can now enter review as pending MotionEvidence through an
explicit user action documented in
[docs/saved-preview-review-evidence-handoff-design.md](docs/saved-preview-review-evidence-handoff-design.md);
saved preview media still cannot create Events, Visits, labels, or truth without
explicit promotion and later review/correction.
The Motion Evidence review UI shows saved preview media/provenance context while
keeping ignore, promote, and correction as explicit steps.
After explicit promotion, Event and Visit detail keep saved preview media
context visible while correction remains the analytics/export truth boundary.
The Streams page also shows recent saved media for each selected Stream so
external_url saved previews or other local image MediaAssets can be explicitly
reused later for synthetic DetectionProposal evidence or pending MotionEvidence.
Streams with at least two saved image snapshots can also run an explicit Check
motion action. If no user Zones exist yet, MockingBird checks automatic activity
areas using motion only; user Zones improve accuracy and privacy/ignore behavior
later. Future classifier/model enrichment belongs on the best snapshot/crop for
a finalized activity session, not each automatic area. Motion checks now classify
activity as new, ongoing, cooldown-suppressed, or no activity; duplicate
suppression is per Activity area, not global to the camera. They also identify a
focused Activity crop plan while preserving the full best snapshot as the
source/context image; crop file creation remains optional future derived context.
Motion results remain candidate activity until explicit review/correction creates
truth for Bird Log and export. Browser-direct Live view is separate from
snapshot capture, monitoring, and review truth. Camera Monitoring Core is
backend-managed, explicit start/stop, external_url first, in-memory for this
phase, and adapter-ready later.
This timeline now summarizes existing proposal evidence, MotionEvidence,
promoted Event/Visit context, inferable ReviewLabel truth, and the next safe
review/export step. It does not run models, poll sources, create Events/Visits
automatically, or create ReviewLabel truth.
If `MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH` is set to a local model file, the
same timeline can explicitly run the optional Local Image Detector on saved
image media. Optional `MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH` may point to a
local labels file when supported. Detector runs create `DetectionProposal`
evidence only; use the demo proposal action when the local detector is not
configured.
The Model Adapters page shows the Local Detector setup/readiness panel with
the exact local env vars, supported image media types, runtime readiness, and a
link back to Streams. Model files are not bundled or downloaded.
For a real local model smoke check, configure the local model path if you have
one, restart the API, capture or import an image, run Analyze image explicitly
from the saved image, review/correct the suggested label, confirm Bird Log, and
export reviewed data.
The source/stream smoke-test hardening plan is documented in
[docs/source-stream-smoke-test-hardening.md](docs/source-stream-smoke-test-hardening.md).
For manual browser/API validation of that same explicit path, use
[docs/source-stream-dev-smoke-checklist.md](docs/source-stream-dev-smoke-checklist.md).
Saved external_url preview media now has a retention report, cleanup dry-run
planner, Saved Media Retention UI, and confirmed low-risk file-only cleanup.
Record deletion, protected cleanup, and background cleanup still require
separate scope and must follow
[docs/external-url-saved-media-retention-design.md](docs/external-url-saved-media-retention-design.md).
The next provider boundary is Folder / trail-cam import, documented in
[docs/folder-trailcam-provider-boundary-design.md](docs/folder-trailcam-provider-boundary-design.md).
It is now represented as a provider configuration/status contract plus an
explicit source-scoped dry-run preview and MediaAsset-only import:
`folder_import_future` stores redacted setup metadata, reports readiness, and
can list candidate/skipped files or copy supported selected/candidate files into
local MediaAssets without creating truth.
The Streams page exposes those preview/import actions for configured
`folder_import_future` Sources, showing candidates, skips, warnings, and created
MediaAssets without exposing the raw folder path.
It still adds no watcher, polling, live playback, media decoding, or background
import behavior. Folder-imported MediaAssets can now become pending
MotionEvidence one at a time through explicit user action, but folder import
itself still creates no MotionEvidence, Events, Visits, labels, or truth. A
batch evidence handoff dry-run can report eligible/skipped imported MediaAssets
without creating records, and a confirmed batch action can create pending
MotionEvidence for eligible imported media only.
That handoff is documented in
[docs/folder-import-evidence-handoff-design.md](docs/folder-import-evidence-handoff-design.md):
promotion and correction remain separate.
The Motion Evidence, Event Detail, and Visit Detail views now show folder-origin
media/provenance context where safe, while correction remains the truth boundary.
Combined provider smoke coverage for `external_url` and `folder_import_future`
is documented in
[docs/source-provider-smoke-flow-hardening.md](docs/source-provider-smoke-flow-hardening.md):
both paths require explicit user actions, keep status routes read-only, and
preserve correction as the truth boundary.
The Dashboard can summarize those provider workflows and next actions, but it
only routes users to explicit Streams, Motion Evidence, Retention, and Review
surfaces.
The next provider boundary decision recommends generic webhook ingest as the
next design-only Source adapter boundary before implementation; see
[docs/next-provider-boundary-decision.md](docs/next-provider-boundary-decision.md).
The generic webhook boundary is documented in
[docs/generic-webhook-provider-boundary-design.md](docs/generic-webhook-provider-boundary-design.md):
`webhook_future` now appears as a Generic webhook ingest provider setup/status
contract. Users can save redacted setup intent and run an explicit payload
validation dry-run at `/api/sources/{source_id}/webhook/validate`, but no
general webhook/media ingest endpoint exists yet. Confirmed metadata-only
motion payloads can create pending MotionEvidence at
`/api/sources/{source_id}/webhook/motion-evidence`, but no media, Events/Visits,
labels, or truth are created; correction remains the review truth boundary.
That metadata webhook path now has backend smoke coverage through validation,
pending evidence, explicit promotion, and correction truth.
The review UI now surfaces safe webhook provenance for webhook-origin
MotionEvidence and promoted Event/Visit detail while treating external labels
and confidence as untrusted evidence metadata only.
The Dashboard now includes an
[MVP readiness overview](docs/mvp-readiness-consolidation.md) for External URL,
Folder / trail-cam import, Generic webhook ingest, and Manual media provider
workflows. It summarizes current support, explicit next actions, live playback
status, and truth boundaries without running providers or creating records.
Use [docs/mvp-demo-script.md](docs/mvp-demo-script.md) for a repeatable local
walkthrough of the MVP spine from Dashboard readiness through provider
workflows, Motion Evidence, correction truth, analytics/exports, classifier
readiness, and saved media retention.
Use
[docs/onboarding-empty-state-polish.md](docs/onboarding-empty-state-polish.md)
for first-run and sparse-data copy rules that keep onboarding read-only and
truth-safe.
Use
[docs/local-mvp-readiness-checklist.md](docs/local-mvp-readiness-checklist.md)
as the local demo/dev readiness gate before selecting riskier provider,
worker, or playback work.
Background workers and live automation are future work. The current lifecycle
boundary is documented in
[docs/worker-lifecycle-boundary-design.md](docs/worker-lifecycle-boundary-design.md):
workers must be explicitly enabled, observable, bounded, and unable to create
review truth.

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

## MVP local demo and smoke check

Use [docs/mvp-demo-script.md](docs/mvp-demo-script.md) for the browser demo
loop from import evidence through ReviewLabel correction and Dataset Export
proof.
It also includes the explicit `external_url` snapshot capture-to-review path:
configure/select Source, fetch preview, save MediaAsset, create pending
MotionEvidence, optionally create synthetic demo DetectionProposal evidence,
reuse saved Stream media from the timeline, inspect lifecycle status, optionally
run an explicitly configured local detector, promote to Event/Visit, correct in
Review Queue, and inspect a reviewed-only export proof record. Detector and
proposal paths create evidence only, create no truth, and this path is not live
video.

```sh
.venv/bin/python -m uvicorn mockingbird.api.main:app --reload
cd web && npm run dev
.venv/bin/python scripts/check_mvp_smoke.py
.venv/bin/python scripts/run_local_image_smoke.py --file /path/to/local-image.jpg --convert
```

The smoke check is read-only. It creates no media, proposals, corrections,
exports, or truth.

## Local image smoke path

With the API running, a developer can import one local image and create demo
DetectionProposal evidence without installing detector dependencies:

```sh
python scripts/run_local_image_smoke.py --file /path/to/local-image.jpg
```

To also convert the first proposal into a reviewable Event/Visit:

```sh
python scripts/run_local_image_smoke.py --file /path/to/local-image.jpg --convert
```

The script prints the MediaAsset, DetectionRun, DetectionProposal, and optional
Event/Visit IDs, plus API hints for `/api/media/{id}`,
`/api/detection-runs/{id}/proposals`, `/api/detection-proposals`, and
`/api/review-queue`. This is a synthetic demo detector path: no model inspects
the media, no ReviewLabel truth is created, and review/correction remains
required before exports, analytics, or classifier readiness treat the label as
truth.

The browser uses the same boundary: start the API and frontend, open Import
Media, import an image, click Create demo proposal, optionally create and
convert it to Event/Visit context, then open Review Queue. This adds no model
runtime and creates no truth on its own. Submit an explicit Review Queue
correction to create ReviewLabel truth, then check Classifier Readiness,
Exports, or Analytics.
After correction, create a reviewed-only Dataset Export to inspect local
dataset records.

## Local detector spike

The Local Image Detector adapter is optional, evidence-only, and disabled until configured with a local model file. No model files are committed or downloaded automatically.

```sh
export MOCKINGBIRD_LOCAL_DETECTOR_MODEL_PATH=/path/to/local-detector.onnx
export MOCKINGBIRD_LOCAL_DETECTOR_LABELS_PATH=/path/to/labels.txt # optional
export MOCKINGBIRD_LOCAL_DETECTOR_CONFIDENCE_THRESHOLD=0.5 # optional
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

Saved preview MediaAssets also appear there as pending evidence context after explicit handoff.

Promoted saved preview evidence can keep that saved media context visible on
Event and Visit detail pages, but no label is truth until correction.

The current local demo loop is import media -> create media-backed Motion Evidence -> promote -> review/correct.

Species suggestion now has a manual/mock evidence surface and a frontend prefill path into Visit correction: suggestions are evidence only until review/correction creates truth, and accepted status after correction is evidence metadata only. See [docs/species-suggestion-adapter-design.md](docs/species-suggestion-adapter-design.md) and [docs/species-suggestion-correction-flow.md](docs/species-suggestion-correction-flow.md).

Visit review UI keeps species suggestions near correction while preserving the correction form as the reviewed truth action.

Reviewed media-backed bird visits can feed the classifier manifest preview and metadata-only backend file export, but only reviewed corrections count as training truth. The frontend can dry-run and create local manifest metadata exports under an ignored export path; the backend can also dry-run future copy-media planning without copying media. MockingBird still does not copy media, train, or run classifier runtime. See [docs/external-training-workspace-template.md](docs/external-training-workspace-template.md), [docs/external-training-workspace-checklist.md](docs/external-training-workspace-checklist.md), [docs/media-copy-export-design.md](docs/media-copy-export-design.md), [docs/external-training-workflow.md](docs/external-training-workflow.md), [docs/classifier-manifest-file-export-design.md](docs/classifier-manifest-file-export-design.md), [docs/custom-bird-classifier-dataset-plan.md](docs/custom-bird-classifier-dataset-plan.md), and [docs/classifier-training-manifest-design.md](docs/classifier-training-manifest-design.md).

SpeciesNet is under docs-only runtime/source review as a future optional suggestion adapter, with a boundary plan before any runtime work. See [docs/speciesnet-runtime-investigation.md](docs/speciesnet-runtime-investigation.md), [docs/speciesnet-source-review.md](docs/speciesnet-source-review.md), and [docs/speciesnet-adapter-boundary-plan.md](docs/speciesnet-adapter-boundary-plan.md).

Before wiring a real detector model, follow [docs/model-adapter-guardrails.md](docs/model-adapter-guardrails.md), [docs/model-selection.md](docs/model-selection.md), the [MegaDetector decision record](docs/detector-decision-megadetector.md), the [MegaDetector runtime plan](docs/megadetector-runtime-plan.md), and the [local setup checklist](docs/megadetector-local-setup.md).

## Not the product center

MockingBird is not centered on Windows USB camera scripts, PowerShell, CLI tools, interval analysis, snapshot loops, ROI language, or debug internals.

Those may exist as implementation details or developer utilities later, but they are not the product.
