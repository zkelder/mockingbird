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
- Local Data backup/recovery and Storage & Retention

The primary navigation flow is Cameras/Streams -> Review Queue -> Bird Log ->
Exports. Advanced evidence, provider diagnostics, and optional analyzers support
that flow without becoming the product center. Product Mode makes current
detector-qualified animal Visits the compact default review task while keeping
legacy activity and developer provenance secondary; see
[review-product-mode-contract.md](review-product-mode-contract.md).

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

Storage & Retention remains local and policy-led: defaults are disabled, server
previews select only validated eligible assets, and confirmed cleanup moves files
to managed recovery before unlinking eligible evidence associations. Primary,
unresolved, reviewed wildlife, export-referenced, incomplete, symlinked, and
otherwise ambiguous media fails closed. Automatic maintenance is bounded to one
app-owned worker, uses a fresh policy pass rather than a browser preview, and
shares its maintenance window with backup and restore.

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

### Observation Engine v2 boundary

Stage 1 is implemented: provider-neutral evidence contracts, an explicit active-provider registry, and a read-only health/capability surface wrap the established timer-driven observer as `SnapshotObservationProvider`. The compatibility provider delegates to the existing bounded snapshot monitor; it creates no parallel runtime, detector, or truth path.
Stage 2 adds the deterministic, shadow-only ordered-frame replay host described in
[observation-replay-benchmark-contract.md](observation-replay-benchmark-contract.md).
It performs no durable product or truth writes. Stage 3 adds the optional
`onnx-cuda` replay provider described in
[onnx-cuda-shadow-provider-contract.md](onnx-cuda-shadow-provider-contract.md).
It performs explicit local-model GPU detection only: no live video, tracking,
evidence selection, Visit proposals, or proposal authority. Stage 4 adds the
distinct replay-first `frame-driven-onnx-cuda` provider described in
[frame-driven-shadow-provider-contract.md](frame-driven-shadow-provider-contract.md).
It schedules that detector from source-relative timestamps, updates a provider-
neutral bounded tracker on each analysis frame, retains portable evidence
candidates, and emits idempotent shadow-only Visit proposals. It still has no
live-stream input, Camera Node analysis stream, high-resolution burst, product
repository dependency, or production proposal authority. CUDA and tracker runtime
types remain behind provider boundaries; product records still contain only
provider-neutral evidence and correction-derived truth.

The Stream-to-proposed-Visit subsystem will be reworked through a strangler
migration, not a product rewrite. A provider-neutral Observation Engine consumes
Stream capabilities and emits only evidence-side `FramePacket`,
`DetectionObservation`, `TrackUpdate`, `EvidenceCandidate`, and `VisitProposal`
facts plus bounded capability/health state. Media pipeline providers own decode,
timestamps, identities, rolling buffers, and high-resolution requests; inference
providers own model execution only; MockingBird tracking and Visit assembly own
temporal continuity, evidence scoring, and proposal semantics. Interpretation is
downstream of assembled Visits; correction remains the first truth write.

`SnapshotObservationProvider` names the current timer-driven path. It remains a
privacy-preserving compatibility provider for lower-capability hardware,
deterministic comparison, and fallback. Future CPU and other accelerated
providers must conform to the same contract; the implemented ONNX Runtime CUDA
provider is replay-only and shadow-only. A completely functional
CPU path and the provider contract remain open and vendor-neutral. Proprietary
acceleration may improve performance but cannot define MockingBird data, truth,
or product behavior. The Raspberry Pi validates one Camera Node provider path;
it does not define the product architecture.

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
browser-playable streams, RTSP, Linux local USB, Windows DirectShow, and the
paired local-LAN Camera Node snapshot adapter.

Adapters sit below provider configuration, Source connection status, and Stream
playback status. They normalize into Source/Stream/MediaAsset/MotionEvidence or
proposal evidence. Provider status does not run providers. Incoming labels or
events do not bypass Review Queue correction.

Guided Camera Editing changes an existing compatible Source/Stream in place.
Its read, validation, impact-preview, and bounded revision-history contracts
redact provider values and credentials; provider type remains fixed. An
application service coordinates a runtime-affecting save with the existing
session manager and durable supervisor, preserving desired monitoring intent,
Zones, Events, Visits, evidence, corrections, organization, map placement,
alerts, and health history. A restart is requested only after explicit
confirmation for an already-armed Stream; capacity remains a waiting state
rather than disabling monitoring.

Provider-specific security, storage, and evidence contracts remain in focused
design documents routed by [AGENTS.md](../AGENTS.md).

Camera Node is an edge adapter, not a parallel product runtime. Its explicit
one-time pairing creates a locally stored masked credential and one selected
opaque camera ID beneath the existing Source/Stream. The main app owns all
Zones, monitoring intent, activity/evidence, Visits, correction truth, backup,
and retention. Node requests are fixed-path, private-LAN-IP-only, bounded, and
redirect-free. Add Camera can request one transient bounded JPEG before a Zone
is drawn; running live/monitoring snapshots use the in-memory frame cache.
Neither preview form is persisted. See
[camera-node-boundary-design.md](camera-node-boundary-design.md).

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

`DurableMonitoringSupervisor` reconciles explicitly enabled supported
live-video Streams with current-process sessions. It is app-owned, starts only
after local persistence initialization, respects one-Stream leases and a small
concurrency cap, waits for a healthy frame before motion evaluation, and uses
deterministic bounded backoff. The persisted policy remains desired state;
runtime checkpoints expose the last-known actual state and are invalidated when
a prior app process ends.

Backup, restore, migration, emergency stop, Source archive, Stop camera, and
shutdown override active runtime. Stop camera also disables durable intent so
it cannot immediately restart. Status reads remain side-effect free. External
snapshot polling and general provider workers remain separate. Future audio
requires its own consent, privacy, retention, dependency, and evidence design;
video arming never enables a microphone.

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
