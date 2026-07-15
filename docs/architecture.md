# MockingBird Architecture

MockingBird is built around a universal outdoor event model.

Source adapters feed media into the platform, but the product is not organized around adapter-specific behavior.

## Conceptual layers

## App experience

- Streams
- Zones
- Events
- Visits
- Review
- Corrections
- Analytics
- Dataset exports

## Product API

- Sources
- Source provider configuration contract
- Source setup review/status contract
- Source connection/provider status contract
- Streams
- Stream playback status contract
- Zones
- Events
- Visits
- Detections
- Review labels
- Dataset exports

## Local intelligence

- Motion/activity detection
- Sampled-frame ingestion boundary between visible streams and frame-plane evaluation
- Lightweight sampler abstraction for supplied frame-plane evaluation
- Best-frame media attachment as optional Motion Evidence context
- Local frame artifacts as future visual evidence references
- Motion Evidence between scoring/evaluation and Event/Visit creation
- Motion Evidence persistence and ignore lifecycle
- SpeciesSuggestion evidence layer between media-backed Event/Visit evidence and review/correction
- SpeciesSuggestion correction flow as a pre-correction assist, not a truth layer
- Animal detection
- Species classification
- Event grouping
- Review prioritization

## Source adapters

Examples for later phases:

- Demo stream
- Manual upload
- Folder import
- RTSP/IP camera
- USB/local camera
- ESP32-CAM
- HTTP snapshot
- Trail-cam import
- Frigate
- Home Assistant
- Blue Iris
- Scrypted
- MQTT
- Webhook

Adapters should normalize into the same source, stream, media, event, and visit model.

The source adapter boundary sits below Source provider configuration, Source
connection status, and Stream playback status. Future adapter work must follow
[source-adapter-boundary-design.md](source-adapter-boundary-design.md) so real
provider code feeds product contracts without replacing the Stream, Zone,
review, correction, export, and analytics loop.

The first recommended adapter boundary is external URL / HTTP still-image
preview/status. Its contract is documented in
[external-url-still-image-provider-contract.md](external-url-still-image-provider-contract.md)
and remains explicit, bounded, local-first, and non-truth.
The Phase 11C preview fetch is an explicit request only: no worker, no storage,
no live playback, and no evidence or truth creation.
Phase 11E adds an explicit preview save boundary:
external_url fetch -> local MediaAsset only -> no truth. See
[external-url-preview-media-asset-handoff-design.md](external-url-preview-media-asset-handoff-design.md).
Phase 11G implements the next boundary:
saved preview MediaAsset -> explicit pending MotionEvidence handoff -> no
Event/Visit or truth until later promotion and correction. See
[saved-preview-review-evidence-handoff-design.md](saved-preview-review-evidence-handoff-design.md).
Phase 11H makes that handoff visible in the Motion Evidence review UI by
showing attached saved media, safe provenance copy, Source/Stream/Zone context,
and explicit pending/ignored/promoted state without creating truth.
Phase 11I carries saved-preview context into the explicit promote/review UI:
Event and Visit detail can show promoted MotionEvidence provenance and saved
local media context, while correction remains the analytics/export truth source.
Phase 12A hardens that source/stream path with backend smoke tests:
configured Source -> setup review -> Stream playback status -> explicit preview
-> saved MediaAsset -> pending MotionEvidence -> explicit promotion ->
review/correction truth. The smoke path adds no provider runtime, live
playback, automation, media decoding, or truth writes before correction.
Phase 12B adds a manual developer/browser checklist for validating the same
explicit flow in the running app; see
[source-stream-dev-smoke-checklist.md](source-stream-dev-smoke-checklist.md).
Phase 12C designs saved preview media retention before any cleanup
implementation. Saved MediaAssets can accumulate, but cleanup must be
user-controlled, dry-run first, and careful not to delete reviewed truth or
break review provenance. See
[external-url-saved-media-retention-design.md](external-url-saved-media-retention-design.md).
Phase 12D implements the read-only saved-preview retention report and cleanup
dry-run planner. It classifies low/medium/high/protected risk from current
links to MotionEvidence, Event/Visit context, and reviewed correction truth, but
does not delete files, delete records, fetch URLs, decode media, or mutate truth.
Phase 12E adds the Saved Media Retention UI as a read-only storage visibility
layer over that report and dry-run planner. It shows risk, linkage, warnings,
and dry-run effects without adding cleanup/delete behavior.
Phase 12F adds explicit low-risk file-only cleanup for unlinked saved preview
media. The cleanup route deletes no MediaAsset records, MotionEvidence, Events,
Visits, ReviewLabels, DatasetExports, or truth, and rejects linked, protected,
unsafe-path, and symlink media.
Phase 13A defines the next provider boundary: Folder / trail-cam import. It is
design-only and keeps local folder batch media under Source/Stream contracts,
explicit import planning, MediaAsset review context, and correction truth. It
adds no folder scan, watcher, polling, import, decoding, or provider runtime.
Phase 13B adds the folder/trail-cam provider metadata/status layer:
`folder_import_future` appears in provider definitions, redacts `folder_path`,
reports setup readiness, and keeps related Stream playback placeholder-only.
It still adds no folder scan, import, copy/reference behavior, MediaAsset,
MotionEvidence, Event/Visit, label, truth, worker, or dependency behavior.
Phase 13C adds the explicit source-scoped folder import preview API. It uses the
configured `folder_path` only when requested, returns relative candidate/skipped
file reports, and creates no MediaAssets, MotionEvidence, Events, Visits,
ReviewLabels, DatasetExports, SpeciesSuggestions, DetectionProposals, or truth.
It adds no watcher, polling loop, media decoding, import/copy behavior, runtime
dependency, or model behavior.
Phase 13D adds explicit source-scoped folder import to MediaAssets only. It uses
the same folder/path guardrails as preview, copies supported files into
MockingBird-managed local media storage, records safe relative-path provenance,
and creates no MotionEvidence, Events, Visits, ReviewLabels, DatasetExports,
SpeciesSuggestions, DetectionProposals, analytics/export truth, watcher,
polling loop, media decoding, dependency, or model behavior.
Phase 13E adds the Streams page UI for folder preview/import. The UI is an
explicit local-media ingest surface: it previews candidate/skipped relative
paths, imports previewed files as MediaAssets only, and leaves MotionEvidence,
Events/Visits, labels, analytics/export truth, and review/correction to later
explicit steps.
Phase 13F designs that later boundary:
folder-imported MediaAsset -> explicit pending MotionEvidence handoff -> explicit
promotion -> Event/Visit review -> correction truth. See
[folder-import-evidence-handoff-design.md](folder-import-evidence-handoff-design.md).
Phase 13G implements the single-media version of that boundary: one
folder-imported MediaAsset can become one pending MotionEvidence through
explicit user action, with duplicate skips by default and no Event/Visit,
ReviewLabel, model output, or truth creation.
Phase 13H adds a batch evidence handoff dry-run for already-imported folder
MediaAssets. It reports eligible, duplicate, skipped, privacy/ignore, and stale
media cases without creating MotionEvidence, Events, Visits, labels, truth,
folder scans, imports, decoding, workers, or model runtime behavior.
Phase 13I adds confirmed batch creation from eligible folder-imported
MediaAssets to pending MotionEvidence. It reuses dry-run eligibility, creates no
Events, Visits, labels, reviewed status, truth, folder scans, imports, decoding,
workers, or model runtime behavior.
Phase 13J polishes folder-origin evidence review and promotion UI. Motion
Evidence can show folder-imported media, safe relative provenance, and
pending/ignored/promoted state; promoted Event/Visit detail can show the same
review context while correction remains the truth boundary.
Phase 14A adds a validation boundary over both implemented provider paths:
`external_url` and `folder_import_future` now share smoke coverage from
Source/status through explicit MediaAsset/evidence/promote/correction flow. It
adds no live playback, automation, worker, watcher, polling, model runtime,
media decoding, or new provider behavior.
Phase 14B lets dashboard/source overview summarize provider readiness and next
actions from read-only status contracts. It routes users to explicit workflows
without fetching provider media, scanning folders, creating evidence, promoting
events/visits, or writing review truth.
Phase 14C chooses generic webhook ingest as the likely next Source adapter
boundary before implementation. The webhook layer should start as design only,
sit below Source provider configuration/status contracts, and map future
incoming media or event candidates into MediaAsset/MotionEvidence evidence
without creating reviewed truth. See
[next-provider-boundary-decision.md](next-provider-boundary-decision.md).
Phase 14D defines that boundary in
[generic-webhook-provider-boundary-design.md](generic-webhook-provider-boundary-design.md).
It keeps webhook ingest local-first, ecosystem-neutral, playback-free by
default, and evidence-only until explicit review/correction.
Phase 14E adds `webhook_future` to provider configuration, Source connection
status, setup review, and placeholder Stream playback contracts. The metadata
layer can show redacted shared-secret readiness and future ingest copy, but it
does not expose webhook endpoints, accept payloads, create media/evidence,
create Events/Visits, write truth, or claim live playback.
Phase 14F adds an explicit webhook payload validation/dry-run API under the
same Source boundary. It classifies generic payloads, validates Source/Stream/Zone
context, and reports candidate mappings while creating no records, fetching no
media, authenticating no payloads, and writing no truth.
Phase 14G adds a confirmed webhook metadata motion route:
webhook motion candidate -> pending MotionEvidence only. It reuses validation,
records safe provenance, and still creates no MediaAsset, Event, Visit,
ReviewLabel, SpeciesSuggestion, DetectionProposal, media file, model output, or
truth.
Phase 14H adds smoke-test coverage for that complete metadata path:
webhook_future Source -> validation dry-run -> pending MotionEvidence ->
explicit promote -> Event/Visit review -> correction truth. Read-only
configuration/status/playback routes remain side-effect free, and webhook labels
stay untrusted metadata until user correction.
Phase 14I makes webhook-origin evidence understandable in the frontend review
loop: Motion Evidence, Event Detail, and Visit Detail can show safe webhook
provenance while correction remains the analytics/export truth boundary.
Phase 15A adds the MVP readiness Dashboard overview as a read-only layer over
implemented provider workflows. It summarizes current support, explicit next
actions, live playback status, and truth boundaries without fetching provider
media, scanning folders, processing webhook payloads, creating evidence,
promoting Events/Visits, or writing review truth.
Phase 15B documents the local MVP demo script:
Dashboard readiness -> provider workflows -> MotionEvidence review/promote ->
Event/Visit correction -> analytics/export/classifier readiness -> saved media
retention. The script validates the product spine without adding runtime
behavior.
Phase 15C adds read-only onboarding and empty-state polish for sparse local app
states. These surfaces may guide users toward explicit provider actions,
MotionEvidence review, Visit correction, analytics, exports, classifier
readiness, and retention, but they must not run providers, fetch media, scan
folders, process webhook payloads, create evidence, promote Events/Visits, or
write reviewed truth.
Phase 15D adds a local MVP readiness checklist. It is a documentation gate over
validation, demo flow, known limitations, artifact safety, and truth boundaries;
it adds no runtime behavior.
Phase 16A defines the worker/lifecycle boundary before background behavior.
Workers are future optional infrastructure below explicit provider actions; they
must be disabled by default initially, observable, bounded, and unable to create
ReviewLabels, reviewed Visits, analytics truth, or export truth. See
[worker-lifecycle-boundary-design.md](worker-lifecycle-boundary-design.md).
Phase 16B adds `GET /api/workers/status` as a read-only visibility layer for
future automation. The status API returns disabled, unimplemented placeholders
only and must not start workers, call providers, create records, or write truth.
Phase 16C adds the Worker Status frontend page and Dashboard link as a read-only
visibility layer over that API. The UI shows future worker placeholders,
summary counts, and false create/truth flags without controls to start, enable,
run, or delete worker behavior.
Phase 16D moves future worker placeholders into a disabled metadata-only worker
registry beneath provider actions. The registry is an attachment point for
status only; it has no executable worker behavior and cannot call providers,
create records, or write truth.

Source provider configuration is the metadata boundary for intended provider
setup. It may store safe setup fields and configured/not-configured markers, but
it must not store raw secrets, connect to sources, decode media, create evidence,
or write review truth.

Source setup review is a read-only product/status boundary over provider
configuration, source connection readiness, and related stream playback status.
It may guide the next setup step, but it must not connect to sources, decode
media, create evidence, write review truth, or create exports.

Manual media provider integration is an explicit local import boundary. Source
setup/status may guide the user to import media for a Source/Stream, and that
import can create reviewable Events/Visits, but reviewed truth still comes only
from review/correction.

Folder/trail-cam provider work is a future local media Source boundary for
trail-camera dumps, NAS folders, and exported image batches. It should follow
[folder-trailcam-provider-boundary-design.md](folder-trailcam-provider-boundary-design.md)
before any folder evidence/review handoff, watcher, polling, truth-affecting
behavior, or delete behavior is added.
The current implementation layer for that provider is configuration/status plus
explicit dry-run preview, explicit MediaAsset-only import, and a compact Streams
page UI for those actions.
The folder-import MediaAsset -> MotionEvidence handoff is implemented for one
media item at a time in Phase 13G. Phase 13H adds a read-only batch dry-run
report for that handoff. Phase 13I adds confirmed batch pending-evidence
creation for eligible imported media. Phase 13J makes that evidence handoff
visible in review/promote UI without adding creation behavior. No folder import
route or status route creates evidence by itself.

The Streams, Stream Detail, and Import Media surfaces present provider
configuration, setup review, connection readiness, playback status, zone editing,
and manual import as one product flow. This UI consolidation does not add live
playback, provider runtime behavior, media decoding, evidence creation, or truth
creation outside explicit import and review/correction paths.

Source connection status is the product boundary between source metadata and
future provider readiness. Providers may feed safe status, field readiness, and
related Stream ids later, but the contract must not connect sources, decode media,
create evidence, write review truth, or create exports by itself.

Stream playback status is the product boundary between visible streams and future
adapter playback. Adapters may feed status, preview references, or local playback
URLs later, but the contract must not create evidence, review truth, exports, or
analytics truth by itself.

## Local-first storage

MockingBird should prefer local storage for media, labels, corrections, metadata, exports, and analytics.

Cloud services may be optional later, but they should not be required for the core product loop.

Saved media retention is a storage boundary. Current retention report and
dry-run routes are read-only; the current cleanup route is file-only and limited
to confirmed low-risk unlinked saved preview media. Future cleanup work must
separate file deletion from record deletion, protect reviewed truth by default,
and report stale or missing media safely without decoding media.

## Single local application runtime

Phase 24A adds a product runtime above the existing API and frontend layers:

- FastAPI remains the product API and lifecycle owner.
- The compiled React application is served from the same local origin after all
  API, health, and documentation routes.
- Stable browser paths restore primary screens and Source/Stream-adjacent detail
  context after refresh or back/forward navigation.
- Startup validates local SQLite integrity and an explicit schema version before
  reporting readiness.
- Shutdown stops process-owned camera sessions and in-memory monitors without
  persisting or automatically restarting them.

The runtime is orchestration, not a new product model or provider adapter. It
creates no evidence, Event, Visit, correction, export, analytics truth, or model
result. Durable camera/monitor desired state remains a separate lifecycle
boundary under [worker-lifecycle-boundary-design.md](worker-lifecycle-boundary-design.md).

## Durable live-stream lifecycle boundary

Phase 24C designed this layer, and Phase 24D implements its inert desired-state
attachment point. Every Stream now receives an `off` monitoring policy and a
`stopped` runtime checkpoint through an explicit schema migration or Stream
creation. Read-only Stream-scoped policy/runtime APIs and Stream Detail status
expose that separation without creating a supervisor or startup behavior.

A future `DurableStreamSupervisor` may reconcile explicitly armed Stream
monitoring policies with backend-owned live camera sessions after application
restart. It must follow
[durable-camera-monitor-lifecycle-design.md](durable-camera-monitor-lifecycle-design.md).

The architecture keeps three concerns separate:

- `StreamMonitoringPolicy` is durable user intent and defaults off;
- `StreamRuntimeCheckpoint` is operational last-known state, never proof that a
  prior process is still running; and
- `LiveCameraSessionManager` continues to own bounded subprocess, frame-cache,
  monitor-thread, and activity-burst resources for the current process.

The first durable boundary covers supported backend-owned RTSP/local USB/Windows
DirectShow live video only. The explicit external URL `SourceMonitorManager`
remains a separate in-memory/provider-worker concern. Status reads remain
side-effect free; live-session quiet-window handoff now runs from the active
monitor tick instead of browser/status polling. Backup/restore holds override
arming, and only an explicitly enabled auto-create policy may produce
needs-review evidence. Correction remains truth. Future audio may reuse
lifecycle/component ownership but requires
separate consent, privacy, retention, dependency, and evidence design.
