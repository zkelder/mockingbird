# MockingBird Architecture

MockingBird is a local-first outdoor event platform organized around a shared
product model. Source adapters and optional analyzers feed evidence into that
model; they do not redefine the product.

## Product and truth flow

```text
Source -> Stream -> Zone-aware activity -> evidence -> Event/Visit review
       -> explicit correction -> Bird Log / analytics / exports / datasets
```

Evidence includes MediaAssets, MotionEvidence, DetectionProposals,
SpeciesSuggestions, best-frame context, and untrusted external metadata.
Evidence can be pending, ignored, promoted, accepted, rejected, or superseded
without becoming dataset truth.

ReviewLabel correction is the dataset-grade truth boundary. Reviewed-only Bird
Log, analytics, classifier readiness, and exports derive from corrections, not
raw model/provider output.

## Conceptual layers

### App experience

- Cameras/Sources and Streams
- Live view and Zone editing
- monitoring and evidence handoff
- Review Queue, Event Detail, and Visit Detail
- Bird Log, Analytics, Dataset Exports, and Classifier Readiness
- Local Data backup/recovery and saved-media retention

The primary navigation flow is Cameras/Streams -> Review Queue -> Bird Log ->
Exports. Advanced evidence, provider diagnostics, and optional analyzers support
that flow without becoming the product center.

### Product API

The FastAPI layer exposes product contracts for:

- Sources, provider configuration, setup review, and connection status
- Streams, playback status, live camera sessions, and lifecycle status
- Zones
- MediaAssets and MotionEvidence
- Events, Visits, DetectionProposals, and SpeciesSuggestions
- review/correction, Bird Log, analytics, and exports
- retention, schema readiness, and backup/recovery

Read/status/preview/dry-run routes are side-effect free unless their contract
explicitly defines a bounded write. Unknown product ids return product-level
errors rather than leaking adapter behavior.

### Product repository and storage

SQLAlchemy models persist product metadata in local SQLite. The product
repository owns product-level reads/writes and must preserve Source/Stream/Zone
relationships, evidence provenance, correction truth, and export context.

Schema compatibility is explicit and versioned. Startup checks integrity and
schema version. Known migrations are forward-only and tested; unsupported newer
or unmigrated older schemas are rejected safely.

Managed media lives under configured local roots. Database and managed media
form one backup graph: backup/restore verifies paths, sizes, hashes, SQLite
integrity, and schema compatibility before mutation. Restore creates a verified
pre-restore safety backup and can roll database and media back together.

### Local intelligence

- deterministic zone-aware motion scoring
- frame sampling and bounded activity sessionization
- Privacy/Ignore suppression
- one-best-frame evidence selection
- optional DetectionProposal or SpeciesSuggestion adapters
- review prioritization and explicit correction

Motion and analyzer output are evidence. Optional analyzers are lazy, local,
user-configured, and unavailable-safe. No model file or runtime download is
required for the core product.

The first visual species-classifier seam is request-bound to one saved Review
Queue image. It chooses a padded credible animal-detection box, then measured
activity bounds, then a full-frame fallback only when no active Privacy/Ignore
Zone would be analyzed. BioCLIP inference is isolated from the long-lived app
process and database transactions, then writes one ranked `SpeciesSuggestion`
atomically after success. Detector evidence, the original frame, and the actual
classifier crop remain separate provenance. A nonblocking single-flight guard
is acquired before image decode, the disposable worker has a hard timeout, and
artifact digests plus OpenCLIP/PyTorch versions are retained without exposing
local paths. On Windows, the spawn arguments carry only bounded metadata and a
shared-memory descriptor; full RGB bytes are not serialized into process
startup.

### Source adapters

Implemented product paths include demo/manual media, explicit external still
images, explicit folder/trail-cam import, metadata-only webhook evidence,
browser-playable streams, RTSP, Linux local USB, and Windows DirectShow.

Adapters sit below provider configuration, Source connection status, and Stream
playback status. They normalize into Source/Stream/MediaAsset/MotionEvidence or
proposal evidence. Provider status does not run providers. Incoming labels or
events do not bypass Review Queue correction.

Provider-specific security, storage, and evidence contracts remain in focused
design documents routed by [AGENTS.md](../AGENTS.md).

## Live camera ownership

`LiveCameraSessionManager` owns bounded process-local camera resources for
supported backend-served live video:

- one camera subprocess/session per Stream
- latest-frame cache used by Live view, explicit capture, and monitoring
- bounded monitor state and activity bursts
- explicit start/stop and graceful application shutdown

The current session manager does not survive process restart. It starts only
after explicit user action and creates no reviewed truth. A browser closing or
status poll does not implicitly define camera policy.

Browser-direct MJPEG/video/HLS playback is separate from backend capture and
monitoring. The external URL snapshot monitor is a separate in-memory provider
path and is not part of durable live-video supervision.

## Durable lifecycle boundary

Three concerns remain separate:

- `StreamMonitoringPolicy`: durable user intent, defaulting to off
- `StreamRuntimeCheckpoint`: operational last-known state, never proof that an
  old process is still running
- `LiveCameraSessionManager`: current-process camera and monitoring resources

A future `DurableStreamSupervisor` may reconcile explicitly armed supported
live-video Streams with current-process sessions. Phase 24E first adds a
disabled, fake-adapter-tested foundation. It must respect one-Stream leases,
deterministic backoff, stop ordering, app-instance reconciliation, and safety
holds.

Backup, restore, migration, emergency stop, Source archive, Stop camera, and
shutdown override arming. Restored armed policy requires explicit resume.
Status reads remain side-effect free. External snapshot polling and general
provider workers remain separate. Future audio requires its own consent,
privacy, retention, dependency, and evidence design; video arming never enables
a microphone.

## Worker boundary

Workers, polling, watchers, queues, and background cleanup are optional
infrastructure underneath explicit provider actions. They begin disabled,
observable, bounded, local-first, and safely stoppable. They may create evidence
only when explicitly scoped and can never create ReviewLabels, mark Visits
reviewed, or create analytics/export truth.

## Dependency direction

Preferred dependency direction:

```text
frontend -> product API -> domain services -> product repository/storage
                              ^
                              |
                 adapters / camera sessions / analyzers
```

Adapters and runtime components depend on product contracts. Product models do
not depend on adapter-specific payloads, FFmpeg details, model outputs, or one
camera ecosystem.

Phase 24 engineering hardening uses targeted extraction rather than a broad
rewrite: lifecycle work should move touched camera/supervisor behavior toward
focused services, and primary frontend work should move touched page behavior
toward focused components/hooks and scoped styles. Refactoring preserves
behavior and remains separate from unrelated features.

## Architecture invariants

- Streams and Zones remain central even when playback is unavailable.
- Detections and suggestions are evidence; correction is truth.
- Provider and status reads are side-effect free.
- Persisted intent and actual runtime state are not conflated.
- Privacy/Ignore Zones, retention, backup/recovery, and storage budgets apply
  before unattended behavior.
- Generated datasets, media, models, benchmarks, and caches stay ignored/local.
- Release acceptance includes contract parity, schema/backup upgrades,
  hardware-free browser coverage, failure injection, and field performance
  budgets from [roadmap.md](roadmap.md).
