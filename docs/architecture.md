# MockingBird Architecture

MockingBird is a local-first outdoor event platform organized around a shared
product model. Source adapters and optional analyzers feed evidence into that
model; they do not redefine the product. Detection, tracking, and
classification are infrastructure that produce evidence; trustworthy
Observations and growing understanding of a place are the product -- see
"Detection is infrastructure" in [product-doctrine.md](product-doctrine.md).

## Product and truth flow

```text
Source -> Stream -> Zone-aware activity -> evidence -> Event/Visit review
       -> explicit correction -> Bird Log / analytics / exports / datasets
```

[product-doctrine.md](product-doctrine.md) names this same chain in target
doctrine vocabulary: Source → Stream → Zone → Activity Session → Visit →
Evidence → Detection Proposal → Interpretation → Review Decision →
Observation → Export/Analytics. The implementation below still uses
Event/Visit/Detection/DetectionProposal/ReviewLabel; see
[glossary.md](glossary.md) for the term-by-term mapping.

Evidence includes MediaAssets, MotionEvidence, DetectionProposals,
SpeciesSuggestions, best-frame context, and untrusted external metadata.
Evidence can be pending, ignored, promoted, accepted, rejected, or superseded
without becoming dataset truth.

ReviewLabel correction is the dataset-grade truth boundary. Reviewed-only Bird
Log, analytics, classifier readiness, and exports derive from corrections, not
raw model/provider output. Unknown and abstained outcomes are valid; nothing
in this flow may quietly convert a proposal, ecological prior, or
language-model output into truth. A ReviewLabel's own provenance decides
whether it is eligible to *be* that truth boundary at all -- see "Review
Decision Provenance," below.

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

The Observation Engine is the provider-neutral detection/tracking/evidence
runtime named in [product-doctrine.md](product-doctrine.md)'s
"Observation-engine direction": it emits evidence-side facts only
(`FramePacket`, `DetectionObservation`, `TrackUpdate`, `EvidenceCandidate`,
`VisitProposal`) plus bounded capability/health state. It is infrastructure
that produces evidence, never reviewed truth by itself, and it is not the
same thing as an Observation (the durable reviewed product object) -- see the
naming note in product-doctrine.md. Media pipeline providers own decode,
timestamps, identities, rolling buffers, and high-resolution requests;
inference providers own model execution only; MockingBird tracking and Visit
assembly own temporal continuity, evidence scoring, and proposal semantics.
Interpretation is downstream of assembled Visits; correction remains the
first truth write.

`SnapshotObservationProvider` names the original timer-driven path. It
remains a privacy-preserving compatibility provider for lower-capability
hardware, deterministic comparison, and fallback -- a complete, functional,
vendor-neutral CPU path stays available through it. The accepted native path
is the `frame-driven-onnx-cuda` provider family: an optional ONNX Runtime
CUDA detector (CUDA execution is mandatory; CPU fallback is rejected), a
provider-neutral bounded frame tracker, a recurrence-aware burst scheduler, a
bounded multi-frame evidence scorer, a shadow Visit-episode assembler, and a
default-off, explicitly activated `candidate_visit` authority mode. TensorRT
remains only a later optimization; proprietary acceleration may improve
performance but cannot define MockingBird data, truth, or product behavior.
The Raspberry Pi validates one Camera Node provider path; it does not define
the product architecture.

Current capability, in pipeline order:

- **Capture / media pipeline**: a paired Camera Node's authenticated, bounded
  multipart-JPEG analysis stream, or the existing durable RTSP/local-USB/
  Windows-DirectShow monitoring path. `LiveCameraSessionManager` owns one
  live capture per Stream (see "Live camera ownership," below, for how it
  and the Observation Engine share one physical Camera Node camera without
  colliding).
- **Detection**: the `onnx-cuda` provider performs local-model GPU detection
  only -- no live video, tracking, evidence selection, or proposal authority
  by itself. A deterministic offline detector precision/recall/calibration
  benchmark, a shadow-only candidate-vs-incumbent comparison tool, and
  multi-scale (tiling) and adaptive motion-proposal benchmarks exist for
  evaluating a detection-recall strategy or a replacement candidate before
  any live change; see "Formal model lifecycle," below.
- **Tracking / Visit assembly**: `ProviderNeutralFrameTracker` updates from
  source-relative timestamps with a bounded reconnect-bridge budget (a
  benign transport reconnect no longer resets a track) and a bounded
  strong/weak/tracker-only evidence hierarchy for sustained multi-minute
  visits. A separate, optional `VisitEpisodeAssembler` decides whether
  temporally adjacent confirmed tracklets belong to one sustained appearance,
  keeping the tracker itself conservative and bounded.
- **Evidence selection**: a recurrence-aware burst scheduler decides whether
  a track update is a genuine burst opportunity or a suppressible recurring
  false positive before requesting a high-resolution capture; bounded,
  deterministic multi-frame evidence scoring then ranks retained candidates
  into a best identification candidate, a best context candidate, a bounded
  alternate set, or an honest no-useful-evidence state, never using species
  identity.
- **Source-resolution lineage**: replay-sourced evidence carries the original
  reviewed frame identity as additive provenance so reviewed truth can join
  to replay-produced candidates without guessing from filename, ordering, or
  geometry; see "Source-resolution evidence contract," below.
- **Candidate Visit authority**: `ObservationAuthorityMode` (`shadow` or
  `candidate_visit`) gates a narrow persistence adapter, reachable only
  through the app's per-Stream Start/Stop Observation control
  (`ObservationEngineSessionManager`), reverting to `shadow` on Stop or any
  session end. It can turn at most one accepted, assembled proposal into one
  bounded, needs-review candidate Visit through the existing
  `VisitModel`/`EventModel` schema; it can never create a `ReviewLabel`, mark
  a Visit reviewed, or write species/analytics/export truth -- only the
  existing, unmodified correction path can.

See [roadmap-history.md](roadmap-history.md) for the stage-by-stage
development record (Stages 1-6.19, Stage 7, Product Vertical Slice v1,
Unified Observation Experience v1) and the linked design documents for each
stage's full contract:
[observation-replay-benchmark-contract.md](observation-replay-benchmark-contract.md),
[onnx-cuda-shadow-provider-contract.md](onnx-cuda-shadow-provider-contract.md),
[frame-driven-shadow-provider-contract.md](frame-driven-shadow-provider-contract.md),
[camera-node-live-shadow-contract.md](camera-node-live-shadow-contract.md),
[multi-frame-evidence-scoring-contract.md](multi-frame-evidence-scoring-contract.md),
[detector-calibration-benchmark-contract.md](detector-calibration-benchmark-contract.md),
[detector-candidate-comparison-contract.md](detector-candidate-comparison-contract.md),
[multi-scale-detector-benchmark-contract.md](multi-scale-detector-benchmark-contract.md),
[adaptive-motion-proposal-benchmark-contract.md](adaptive-motion-proposal-benchmark-contract.md),
[temporal-review-capture-contract.md](temporal-review-capture-contract.md),
[session-timeline-contract.md](session-timeline-contract.md),
[burst-scheduler-contract.md](burst-scheduler-contract.md),
[evidence-benchmark-contract.md](evidence-benchmark-contract.md),
[reviewed-replay-lineage-contract.md](reviewed-replay-lineage-contract.md),
[sustained-visit-continuity-contract.md](sustained-visit-continuity-contract.md),
[tracklet-visit-assembly-contract.md](tracklet-visit-assembly-contract.md),
[candidate-visit-authority-contract.md](candidate-visit-authority-contract.md),
[reconnect-continuity-contract.md](reconnect-continuity-contract.md),
[observation-engine-product-control-contract.md](observation-engine-product-control-contract.md),
[unified-observation-panel-contract.md](unified-observation-panel-contract.md),
[detection-quality-accounting-contract.md](detection-quality-accounting-contract.md),
[localization-attribution-contract.md](localization-attribution-contract.md),
[rejected-detection-attribution-contract.md](rejected-detection-attribution-contract.md).

### Detection Quality Accounting

Treat vision-pipeline quality as separately measurable stages rather than one
generic "accuracy" concept, and prefer fixing the weakest relevant stage over
reflexively replacing a model (see
[product-doctrine.md](product-doctrine.md)). Current stage-to-component
mapping:

1. **capture availability** -- Camera Node/RTSP/USB/DirectShow connection and
   reconnect handling; camera/observation health reporting.
2. **capture quality** -- exposure, resolution, and frame-rate facts a Source
   actually reports (see "Capability-aware UX," below).
3. **activity detection** -- zone-aware motion scoring / the `onnx-cuda`
   detector's raw call rate.
4. **animal presence** -- detector precision/recall on the calibration
   benchmark cohort.
5. **localization/tracking** -- `ProviderNeutralFrameTracker`,
   reconnect-continuity bridging, sustained-visit continuity.
6. **Visit assembly** -- `VisitEpisodeAssembler`, the burst scheduler's
   recurrence/novelty decisions.
7. **evidence selection** -- multi-frame evidence scoring
   (`evidence_scoring`).
8. **source-resolution crop quality and lineage** -- reviewed-replay
   lineage, best-frame media attachment.
9. **broad classification** -- not cleanly separated from species ranking
    today; the detector's animal/person/vehicle category (stage 4) is the
    closest existing coarse signal.
10. **species candidate ranking** -- the optional local BioCLIP adapter's
    ranked `SpeciesSuggestion` output, produced directly from a crop with no
    intermediate broad-taxon step; not yet accuracy-validated against
    representative reviewed truth (see [roadmap.md](roadmap.md) Phase 2).
11. **calibration** -- `detector-calibration-benchmark-contract.md`'s
    threshold-grid scoring exists for the detector; classifier-side
    calibration does not yet exist.
12. **abstention** -- not yet implemented anywhere in the pipeline; an
    explicit "not confident enough to identify" outcome remains open work.
13. **Observation creation** -- not yet implemented as a distinct step; a
    candidate Visit is the closest current equivalent.
14. **human confirmation/review** -- Review Queue, `ReviewLabel` correction.

Rejected-candidate / counterfactual auditing is part of this accounting:
retain bounded, privacy-conscious diagnostic information about rejected
activity (reason counters, policy/version identifiers, bounded representative
samples, stage-of-rejection information, temporary retention) rather than
either discarding rejection reasons entirely or permanently storing every
rejected frame. The burst scheduler's suppression-reason bookkeeping and the
calibration benchmark's false-negative/below-threshold classification are the
existing precedent for this pattern.

Detection Quality Accounting v1 (see
[detection-quality-accounting-contract.md](detection-quality-accounting-contract.md))
formalizes the stage-4-through-6 slice of this accounting motivated by the
2026-08-10 real-field false-candidate finding: bounded, model-neutral
detector-confidence/evidence lineage (`contracts.ConfidenceEvidenceSummary`)
now survives from detection through track, tracklet, and assembled Visit
proposal instead of being discarded at proposal assembly; a pure six-stage
accounting report (`detection_quality_accounting.py`) covers animal-presence
proposal through candidate Visit creation; and a SHADOW-only, deterministic
admission-policy evaluator (`admission_policy.py`) compares the current
(confidence-blind) production behavior against candidate confidence/temporal
policies on real reviewed historical data, without granting any candidate
policy production authority. A standing rejected-candidate record wired into
a *live* session (previously open) is now covered for admission outcomes by
Rejected / Suppressed Detection Attribution v1, below; representative
difficult-case slices as a standing benchmark structure and the promotion
decision this contract's "Production authority gate" describes remain open.

Localization Attribution / Detection Geometry Lineage v1 (see
[localization-attribution-contract.md](localization-attribution-contract.md))
answers stage 5's own open question after two independent real Camera Node
sessions each showed a genuine, visible bird with a persisted evidence box
that missed it entirely: bounded, model-neutral geometry lineage -- the raw
box behind every retained confidence sample
(`contracts.DetectionEvidenceSample.bounding_box`), the exact source offset
a track's current box was last genuinely established at
(`contracts.TrackUpdate.bounding_box_source_offset_ms`), and a small,
per-evidence-item fact naming which kind of observation supplied one
persisted candidate's box and whether that box's own image provably
represents the same moment (`contracts.GeometryAttribution`) -- now flows
from detection through to the persisted `MediaAsset`
(`geometry_attribution_json`, schema 33). A pure, deterministic diagnostic
(`localization_attribution.classify_localization_attribution`) classifies a
localization failure into `detector_off_target`, `tracker_drift`,
`evidence_geometry_misaligned`, `detector_hit_then_lost`, or (never
guessed) `insufficient_geometry_lineage`, using only already-retained
lineage facts -- never pixel content. Tracing this path found the box a
reviewer actually sees, for any real live Camera Node candidate, always
comes from a high-resolution evidence burst captured measurably later than
the analysis-frame detection that triggered it (`camera_node_live.py`), and
that the transport's own already-computed capture latency
(`request_to_capture_ms`) was previously discarded before persistence
rather than retained as this diagnostic fact. This is measurement only:
no detector, tracker-policy, evidence-selection, or admission-gate behavior
changed.

Rejected / Suppressed Detection Attribution v1 (see
[rejected-detection-attribution-contract.md](rejected-detection-attribution-contract.md))
answers a narrower, complementary question the same 2026-08-11 session's own
disclosed incidental finding raised: a real bird visible in one candidate's
evidence imagery, near the feeder, was structurally unconnected to that
candidate's own track, and the session's own report had to conclude
whether MDv5 ever detected that specific bird was unrecoverable, because a
live session's own suppressed-proposal facts were transient by design.
Tracing the pipeline found three precise loss points: raw per-frame
detector output (`ObservationResult.detection_observations`) was computed
every inferred frame and never read by the live session driver at all;
a track generation the tracker itself never confirmed left no trace once
its generation ended (correctly out of scope for Visit assembly, but also
retained nowhere else); and a non-created admission outcome collapsed to
one bare `{reason: count}` in-memory tally, discarding the proposal's own
id, lineage, and confidence/geometry evidence. `mockingbird.observation.
counterfactual_lineage` adds one bounded, local-only, per-session
standing ledger (`CounterfactualLedger`, capped by both count and age,
deterministic oldest-first eviction) of three small record types --
raw detections (including an explicit "detector ran, found nothing"
heartbeat, distinguishing a genuine negative from an idle-cadence gap),
track-generation outcomes (confirmed or rejected), and proposal admission
outcomes (every outcome, not only suppressed ones) -- reusing
`ConfidenceEvidenceSummary`/`GeometryAttribution`'s own vocabulary rather
than inventing a parallel one. A pure, deterministic diagnostic
(`counterfactual_lineage.classify_rejection_attribution`) classifies a
queried region/time window into `detector_miss`, `detector_hit_then_
tracker_lost`, `detector_hit_then_suppressed`, `tracker_drift`,
`admission_rejected`, `visit_created`, or (never guessed, and never a
false `detector_miss` from an evicted/partial window)
`insufficient_counterfactual_lineage`. A new read-only API route
(`GET /api/streams/{stream_id}/observation/counterfactual`, bounded
time-window and optional region-of-interest query params) and a small
Detection Quality Accounting integration
(`admission_records_from_counterfactual_ledger`) round out the query/
accounting surface, without a second review UI or metrics universe. This
is measurement only: no detector, tracker-policy, Visit-assembly, or
admission-gate behavior changed.

### Review Decision Provenance

`ReviewLabel` had no durable reviewer-origin identity at all before this
milestone (see
[review-decision-provenance-contract.md](review-decision-provenance-contract.md)):
a real `ReviewLabel` an LLM/agent wrote through the genuine `POST
/api/review-labels` path -- exactly what the 2026-08-10 fresh-cohort
candidates were -- was structurally indistinguishable anywhere downstream
from a genuine human correction. `mockingbird.review_provenance` (pure,
dependency-free) now names four provenance states -- `human`,
`imported_curated` (this product's own demo-seed content), `agent_diagnostic`
(an LLM/model/automation assessment), and `legacy_unattributed` (a
pre-migration row, backfilled by schema v32, deliberately still treated as
authoritative for backward compatibility) -- and the one function,
`is_authority_eligible`, that decides whether a given origin may establish
or correct durable reviewed truth. `ProductRepository.
_create_review_label_in_session` is the sole place that ever flips a
Visit/Event to `"reviewed"`; it now does so only for an authority-eligible
origin, which is sufficient to keep Bird Log, Wildlife Insights, Dataset
Export, and classifier training manifests correct without touching their
own read paths, since all of them key off `review_status`/`reviewed_label`
rather than raw `ReviewLabel` existence. Omitting provenance at the API
boundary never defaults to `"human"`; the product's own interactive frontend
is the one place that explicitly stamps it. A future agent-assisted field
cohort uses the same `POST /api/review-labels` endpoint with an explicit
`agent_diagnostic` origin -- no second review system -- durably recorded but
never authoritative.

### Formal model lifecycle

A candidate detector/classifier does not gain production authority merely
because it is newer or appears better informally. The target sequence is:

candidate → reproducible dataset snapshot → stage-specific benchmark →
difficult-case evaluation → incumbent comparison → shadow processing →
calibration → resource-cost evaluation → promotion decision → versioned
deployment → monitoring → rollback/retirement

Current prior art covers the early-to-middle stages for the detector: a
candidate (for example the evaluated `spruce` MegaDetector build) is scored
against a reproducible reviewed cohort
([detector-calibration-benchmark-contract.md](detector-calibration-benchmark-contract.md)),
compared against the MDv5 incumbent on identical data
([detector-candidate-comparison-contract.md](detector-candidate-comparison-contract.md)),
and evaluated through the shadow-only Observation Engine pipeline before any
live change. Difficult-case evaluation exists narrowly today (a small-subject
cohort for the multi-scale benchmark); representative slices for common
species, uncommon species, unknown/unrepresented species, partial/occluded
animals, multiple animals, small/distant subjects, feeder obstruction, motion
blur, poor lighting/dawn/dusk, non-birds, and empty backgrounds do not yet
exist as a standing benchmark structure. A formal promotion-decision rule,
versioned deployment/monitoring, and rollback/retirement policy do not yet
exist; see [roadmap.md](roadmap.md) Phase 2.

Reviewed truth may become valuable training data, but a reviewed
Visit/Observation does not automatically enter a training dataset.
[custom-bird-classifier-dataset-plan.md](custom-bird-classifier-dataset-plan.md)
and
[classifier-training-manifest-design.md](classifier-training-manifest-design.md)
define the current manifest/export boundary; provenance, crop/evidence
quality, ambiguity, duplicates/Visit leakage, uncertain labels, source
lineage, user-contribution policy, and train/validation/holdout separation
are additional eligibility considerations from
[product-doctrine.md](product-doctrine.md) not yet fully reflected in that
plan (see [roadmap.md](roadmap.md) Phase 8).

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
Neither preview form is persisted. Repairing an existing camera's pairing (for
example after a revoked or lost credential) reuses the same one-time-code
consumption path as first-run pairing. A real defect in this path was found
and fixed: the client used to conflate the Node's "this code does not match
at all" (401) response with "some earlier attempt already consumed this
code" (409) into the same "pairing code was rejected" text, and the repair
page had no way to resume a pairing that had already succeeded server-side
but was never saved before an interruption. Repair now distinguishes the two
rejection reasons and can resume an orphaned, already-succeeded pairing. See
[camera-node-boundary-design.md](camera-node-boundary-design.md).

### Capability-aware UX

Provider abstractions stay hardware-agnostic underneath, but status/health
surfaces report actual hardware capabilities honestly rather than showing a
control that would only fail. The current precedent is narrow: a Stream with
no integrated observation runtime reports that honestly instead of showing a
Start button, and Observation/camera health surfaces a plain-language reason
rather than raw provider error text. Extending the same honesty to source
resolution, still-capture support, live/video capability, frame rate,
exposure controls, a high-resolution evidence path, hardware timestamps, and
optional controls such as PTZ/audio is future work; see
[product-doctrine.md](product-doctrine.md) "Capability-aware UX."

### Source-resolution evidence contract

For important evidence, lineage should make it possible to trace: original
source resolution → selected source frame → source-coordinate crop → crop
dimensions → any subsequent transform/resize, so a user or diagnostic can tell
whether a crop actually came from the highest-resolution available source
rather than trusting an ambiguous label. The reviewed-replay lineage
contract already propagates original reviewed frame identity through replay
(`FramePacket` → `DetectionObservation` → `TrackUpdate` → `EvidenceCandidate`
→ `VisitProposal`), refusing to join on coincidental equality, filename,
ordering, timestamp, or geometry. Best-frame media attachment carries the
saved-media side of this chain. Treating both as one formal evidence-lineage
contract, instead of growing a new per-feature lineage field each time, is
open work; see
[reviewed-replay-lineage-contract.md](reviewed-replay-lineage-contract.md) and
[best-frame-media-attachment-design.md](best-frame-media-attachment-design.md).

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

For a paired Camera Node Stream, the Observation Engine's own analysis-stream
connection and `LiveCameraSessionManager`'s legacy live-view/monitoring
connection both want the same physical camera's single capture lock. An
explicit, revocable capture-ownership hand-off --
`LiveCameraSessionManager.pause_for_observation`/`resume_after_observation`,
called by the Observation session before it starts pulling frames and from
its outermost exit handling on every exit path -- prevents the two from
colliding into contended captures and a falsely-reported "Camera Failed"
live view; a plain Start against the paused legacy session is refused rather
than racing a second capture in, and an explicit Stop of that session always
wins over a later automatic resume. See "Camera ownership vs. the legacy
live-view/monitoring session" in
[observation-engine-product-control-contract.md](observation-engine-product-control-contract.md).

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

Targeted extraction is preferred over a broad rewrite: lifecycle work should
move touched camera/supervisor behavior toward focused services, and primary
frontend work should move touched page behavior toward focused
components/hooks and scoped styles. Refactoring preserves behavior and remains
separate from unrelated features.

## Local product packaging and lifecycle

MockingBird's runtime architecture -- one FastAPI process serving both the
product API and the built frontend from the same origin, backed by local
SQLite -- is host-neutral by construction; nothing about it is
Windows-specific. Phase 27A (see
[local-product-packaging-design.md](local-product-packaging-design.md))
packages that same architecture as a self-contained "unpack and run" bundle
with a real embedded Python runtime, first on Windows, without introducing a
second UI runtime, a container, or a service-manager dependency. Making
service lifecycle, upgrades, recovery, migrations, health, detector setup,
and storage management fully product-managed rather than developer-operated
is [roadmap.md](roadmap.md) Phase 4; see "Installation and appliance
experience are product features" in
[product-doctrine.md](product-doctrine.md).

`scripts/deploy_windows_dev.py` (see
[windows-dev-deployment-design.md](windows-dev-deployment-design.md)) is
separate developer tooling for deploying a development build to a real
Windows/GPU host. It is not part of the product's install/upgrade path and
must not gain product behavior of its own.

First-run state (`app_setup_state`, schema 29) is ordinary product state,
seeded once from the one-time "was this database just created" fact
`initialize_database` already computes, never recomputed from current
Source/Stream counts. A small `runtime_state` module (deliberately dependent
on neither `runtime.py` nor `api/main.py`, which already depend on each
other in narrow, deferred ways) tracks the previous-shutdown marker and the
fixed local log location; both are best-effort local facts, never required
for startup to proceed.

## Architecture invariants

- Streams and Zones remain central even when playback is unavailable.
- Detections and suggestions are evidence; correction is truth; unknown and
  abstained outcomes are valid.
- Detection, tracking, and classification are infrastructure; trustworthy
  Observations and growing understanding of a place are the product.
- Provider and status reads are side-effect free.
- Persisted intent and actual runtime state are not conflated.
- Privacy/Ignore Zones, retention, backup/recovery, and storage budgets apply
  before unattended behavior.
- Generated datasets, media, models, benchmarks, and caches stay ignored/local.
- A candidate detector/classifier does not gain production authority without
  reproducible incumbent comparison; see "Formal model lifecycle," above.
- Release acceptance includes contract parity, schema/backup upgrades,
  hardware-free browser coverage, failure injection, and field performance
  budgets from [roadmap.md](roadmap.md).
