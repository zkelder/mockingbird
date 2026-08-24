# Runtime Map

A from-the-code orientation for someone opening this repository for the
first time. [architecture.md](architecture.md) is the authoritative
component/data-flow contract; this document is a shorter, more concrete
companion that answers "which file actually does this, and is it production
or research?" It was produced by tracing real imports, call sites, routes,
and tests (not by intuition) as part of the Runtime Simplification / Code
Archaeology + OSS Readiness milestone. Where this document and
architecture.md disagree, architecture.md wins; file this doc's line as
stale.

## The product path, in one page

```text
Camera Node / Provider  (mockingbird_node/, source_providers/)
        |
Source -> Stream        (repository/product_repository.py, api/main.py)
        |
camera ownership          <- LiveCameraSessionManager vs Observation Engine
        |                     (see "Camera ownership," below)
Zone-aware activity       <- one of three lanes, resolved per-Stream by
        |                     observation/unified_status.py
        v
   +---------------------+---------------------------+
   |                      |                            |
camera_node_engine    live_monitoring              snapshot_monitor
(observation/*)       (motion/*, monitoring/*)     (monitoring/source_monitor.py)
   |                      |                            |
   +---------- Visit / EventModel (storage/models.py) -+
        |
Evidence (MediaAsset, VisitEvidenceLinkModel)
        |
species suggestion   (species/*, evidence only)
        |
Review Decision       (ReviewLabelModel, the one truth write)
        |
Observation (today: a reviewed Visit)
        |
Today in Your Yard / Place Intelligence / history
   (product_repository.py dashboard_summary, analytics/*)
```

Doctrine names this same chain Source -> Stream -> Zone -> Activity Session
-> Visit -> Evidence -> Detection Proposal -> Interpretation -> Review
Decision -> Observation -> Export/Analytics
([product-doctrine.md](product-doctrine.md)). The implementation still uses
`Event`/`Visit`/`Detection`/`ReviewLabel` vocabulary; see
[glossary.md](glossary.md) for the full term-by-term mapping. Detection and
tracking are infrastructure; the Visit/Review/Observation/Place chain is the
product.

## Camera ownership

Two independent, process-wide singleton managers exist in `api/main.py`,
each internally keyed by `stream_id` (a dict, not one shared buffer) so
"process-wide singleton" does not mean "not Stream-scoped" -- every actual
resource is per-Stream:

- **`LiveCameraSessionManager`** (`playback/live_camera_session.py`) -- the
  original backend-owned live-view/monitoring session: one camera
  subprocess/session per Stream, a latest-frame cache
  (`playback/live_frame_cache.py`), bounded zone-aware motion evaluation
  (the `motion/` package), and activity-burst handling. It drives RTSP/local
  USB/Windows DirectShow cameras directly (`playback/rtsp_bridge.py`,
  `local_camera_bridge.py`, `windows_camera_bridge.py`) and can *also* drive
  a paired Camera Node for plain Live view via
  `playback/camera_node_bridge.py`'s `CameraNodeSnapshotProcess`.
- **`ObservationEngineSessionManager`** (`observation/engine_runtime.py`) --
  the accepted native detection/tracking engine: one bounded background
  thread per Stream running its own asyncio loop, reachable only through
  **Start observing** for a paired Camera Node Stream.

Both can want the same physical Camera Node camera's one capture lock at
once. `_EngineSession` calls
`LiveCameraSessionManager.pause_for_observation`/`resume_after_observation`
around every Observation session (see "Camera ownership vs. the legacy
live-view/monitoring session" in
[observation-engine-product-control-contract.md](observation-engine-product-control-contract.md)
and [architecture.md](architecture.md)'s "Live camera ownership"). This is a
deliberate, explicit, tested hand-off -- **not** two competing owners that
happen to coexist. If you touch either manager, re-read that contract
section first; the failure mode this prevents (a live view falsely
reporting "Camera Failed" while Observation runs) was a real, fixed defect.

A second, different hazard in this same seam was found by the Runtime
Simplification / Code Archaeology milestone and closed on both sides by the
following one: `LiveCameraSessionManager`'s own **durable** monitoring policy
(`StreamMonitoringPolicyModel`, the thing "Enable monitoring"/"Disable
monitoring" arms) has no provider-type gate in `playback.live_camera_session`
itself -- `camera_node` deliberately remains in `SUPPORTED_SESSION_TYPES`
because the legacy session still needs to serve plain Live view for a Camera
Node Stream (above). Two frontend surfaces
(`web/src/components/LiveCameraOverview.tsx`, embedded by both
`DashboardPage.tsx` and `StreamsPage.tsx`) used to render that same toggle
unconditionally for every camera tile, including a paired Camera Node one --
arming it there would durably start the legacy zone-motion path alongside
the accepted engine on the same camera, with none of Stage 7's admission
gate, and keep silently resuming every time Observation later stopped
(`resume_after_observation`). The toggle is now hidden for `camera_node`
tiles in that one shared component (matching the "Show/Stop live view"
exclusion already beside it).

**Camera Node monitoring-ownership rule** (CAMERA NODE LEGACY-MONITORING
BACKEND GUARD v1, closing the gap the paragraph above left open -- "a raw
API call is also safe" no longer needs an asterisk):

```text
Camera Node:
  Live view              = supported (LiveCameraSessionManager, unchanged)
  Observation Engine     = canonical monitoring
  legacy durable monitoring = forbidden
```

The backend now enforces this at every place that can arm
`StreamMonitoringPolicyModel.mode = "armed"`, not only the UI:
`ProductRepository._reject_camera_node_legacy_monitoring_enable` is the one
predicate shared by both authoritative mutation call sites --
`set_stream_monitoring_enabled` (the Enable-monitoring toggle/API) and
`complete_camera_setup` (Add Camera's own `enable_monitoring` flag, a second,
independent arming path this milestone found by tracing rather than
assuming the toggle was the only one) -- plus a narrower defensive filter in
`list_enabled_monitoring_candidates` so the durable supervisor can never
treat a stale pre-fix `armed` camera_node row as work (it would otherwise
actually start a real session: `LiveCameraSessionManager` genuinely supports
`camera_node`, so nothing else would stop it). Disabling stays unguarded and
always safe/idempotent, including recovery from stale historical state. The
`CameraSetupPage.tsx` "Start watching" checkbox this section used to flag as
a still-open follow-up UI fix (unconditionally rendered for every provider,
including `camera_node`) was closed by v0.1 Acquisition/Ingest
Interoperability v1 (2026-08-22): the wizard now conditionally hides the
checkbox for `camera_node` and shows explanatory text instead, confirmed
current as of Camera / Source + Multi-Camera Maturity v1's own archaeology
pass (2026-08-23) -- corrected here since this doc had drifted stale on that
one point.

Forbidding legacy durable monitoring for Camera Node used to also mean no
coverage: only that legacy path wrote `MonitoringExposureIntervalModel`, the
table the Today / Place Activity Report's coverage figure reads, so a
Camera Node Place monitored exclusively through Observation Engine
permanently reported 0%/withheld coverage regardless of real activity.
Today Coverage Truth v1 closed that gap by making `ObservationEngineSession
Manager`/`_EngineSession` a second, independent writer of the exact same
table -- see [todays-coverage-truth-contract.md](todays-coverage-truth-contract.md).

## Lane resolution: the one place that picks a runtime

`observation/unified_status.py::resolve_observation_runtime` is the single
function that decides which of three real runtimes owns a given Stream's
**Start observing** / **Stop observing** button, using only already-stored
Source/Stream configuration (no network probe):

| Source configuration | Lane | Runtime |
| --- | --- | --- |
| provider `camera_node` | `camera_node_engine` | `ObservationEngineSessionManager` (Stage 5/7 frame-driven engine) |
| `live_stream_type` in `{rtsp, local_usb, windows_dshow}` | `live_monitoring` | `StreamMonitoringPolicy` + `DurableMonitoringSupervisor` + `LiveCameraSessionManager` |
| provider `external_url`, plain still-image | `snapshot_monitor` | `SourceMonitorManager` wrapped as `SnapshotObservationProvider` |
| demo, manual media, folder/webhook import, unimplemented future adapter | `unavailable` | none -- an honest "not available" status, never a Start button that would only fail |

This is the answer to "are there duplicate runtime entry points": there is
exactly one resolver, and it is a router, not a reimplementation -- each
lane calls the pre-existing, unchanged runtime for that Stream type. See
[unified-observation-panel-contract.md](unified-observation-panel-contract.md).
`GET/POST /api/streams/{id}/observation/{status,start,stop}` in
`api/main.py` is the one route family; the frontend has one panel,
`web/src/components/ObservationControlPanel.tsx`.

## The accepted engine (`camera_node_engine` lane)

In pipeline order, all under `src/mockingbird/observation/`:

1. **Analysis transport**: `camera_node_live.py` (`CameraNodeHttpTransport`,
   `CameraNodeAnalysisSource`, `LiveCameraNodeShadowSession`) pulls a
   bounded multipart-JPEG analysis stream from the paired Camera Node.
2. **Detection**: `onnx_provider.py` (`OnnxCudaObservationProvider`) runs
   the local MDv5 ONNX model on CUDA only (no CPU fallback);
   `mdv5_decoder.py` is its output decoder.
3. **Tracking**: `frame_tracker.py` (`ProviderNeutralFrameTracker`) plus
   `reconnect_continuity.py` (a bounded reconnect-bridge budget so a benign
   transport reconnect does not reset a track), composed by
   `frame_driven_provider.py` (`FrameDrivenObservationProvider`).
4. **Evidence bursts**: `burst_scheduler.py` decides whether a track update
   is a genuine burst opportunity before requesting a high-resolution
   capture; `localization_attribution.py` attaches geometry lineage (which
   observation actually established a persisted box);
   `session_timeline.py`/`media_contracts.py` carry per-session/per-frame
   bookkeeping.
5. **Visit assembly**: `visit_episode_assembler.py`
   (`assemble_visit_episodes`, `build_tracklets`) plus
   `evidence_scoring.py` (bounded multi-frame evidence scoring into
   `identification`/`context`/`alternate` roles).
6. **Candidate authority**: `candidate_visit_adapter.py` +
   `candidate_visit_authority.py` (`ObservationAuthorityMode.shadow` /
   `.candidate_visit`) gate a narrow persistence path;
   `candidate_quality_gate.py::evaluate_evidence_admission` is the last,
   conservative admission check before anything is written.
7. **Counterfactual/diagnostics** (measurement only, changes no behavior):
   `counterfactual_lineage.py` (a bounded per-session ledger of raw
   detections, track-generation outcomes, and admission outcomes, queried
   through `GET /api/streams/{id}/observation/counterfactual`),
   `detection_quality_accounting.py` (offline six-stage accounting report),
   `admission_policy.py` (SHADOW-only candidate admission-policy
   evaluation, never production-authoritative), `evaluation_governance.py`
   (keeps agent/diagnostic assessments out of training/promotion truth).

`engine_runtime.py::ObservationEngineSessionManager` composes steps 1-6
unchanged. `contracts.py` is the shared, dependency-light type vocabulary
(`FramePacket`, `DetectionObservation`, `TrackUpdate`, `EvidenceCandidate`,
`VisitProposal`, ...) essentially every module above imports; if you are
looking for "the schema of an in-flight detection," start there.

## The legacy lanes (`live_monitoring` and `snapshot_monitor`)

Not superseded -- these are the real, current production runtime for every
Stream that is not a paired Camera Node:

- **`live_monitoring`** (RTSP / local USB / Windows DirectShow): the
  `motion/` package (`scoring.py` zone-aware motion scoring,
  `activity_session.py`, `tracked_activity.py`, `object_tracking.py`
  optional MDv5/`detectors/megadetector_adapter.py` proposal,
  `activity_crop.py`, `high_resolution_evidence.py`,
  `local_activity_diagnostic.py`) driven from `api/main.py` and persisted
  through `product_repository.py`. `motion/effective_primary.py` picks the
  best evidence frame for these Visits (extended, not replaced, to also
  recognize the new engine's evidence roles -- see below).
  `monitoring/durable_supervisor.py` reconciles armed
  `StreamMonitoringPolicy` rows with running sessions after a restart.
- **`snapshot_monitor`** (`external_url` still-image Source): the original
  timer-driven path. `monitoring/source_monitor.py::SourceMonitorManager`
  does the polling; `observation/snapshot_provider.py::
  SnapshotObservationProvider` wraps it in the same `ObservationProvider`
  shape the accepted engine uses, so both are interchangeable inside
  `observation/registry.py::ObservationEngineRegistry` for replay/benchmark
  tooling. `api/main.py::get_source_monitor_manager()` is the one
  production instance.

These exist because not every camera has Camera Node hardware or GPU
inference available -- `SnapshotObservationProvider` is explicitly kept as
"a complete, functional, vendor-neutral CPU path" (architecture.md). Treat
both as **KEEP**, not legacy cruft.

## Evidence selection: two resolvers, two lanes, one schema

`motion/effective_primary.py::select_effective_primary` (legacy-lane
evidence, extended additively for the new engine's `identification`/
`context`/`alternate` roles) and `observation/evidence_scoring.py` (the new
engine's own multi-frame scorer) are **not** competing implementations of
the same thing -- they pick the best evidence for two different capture
pipelines that both write into the same `VisitEvidenceLinkModel`/
`MediaAsset` schema and are rendered by the same
`web/src/components/VisitEvidenceSequence.tsx`. If a change needs "pick a
different frame as primary," check which lane produced the Visit
(`event_type == "observation_engine_candidate"` marks the new engine)
before touching either resolver.

## Species suggestion vs. confirmed truth

`species/automatic_identification.py` orchestrates a suggestion run;
`species/bioclip_adapter.py` calls the local BioCLIP runtime;
`species/bioclip_runtime.py` resolves the model/labels/embedding-cache
bundle from either a packaged build or a dev-checkout env-var setup;
`species/classifier_input.py::resolve_classifier_input` picks the best
available image tier (same-frame crop > derived crop > full frame) for that
call, wired into `product_repository.py`. All of this produces a
`SpeciesSuggestionModel` row -- **evidence**, never truth, however
confident. `species/bioclip_evaluation.py` is a separate, **research**
offline-only accuracy tool (`scripts/evaluate_bioclip_field_truth.py`)
that scores already-stored suggestions against reviewed corrections; it
never runs a model or writes product state.

## Review Decision: the one truth write

`review_provenance.py` (pure, dependency-free) defines who/what may write
truth. `ProductRepository._create_review_label_in_session`
(`repository/product_repository.py`) is the **sole** place that ever sets
`VisitModel`/`EventModel.review_status` to `"reviewed"`, and only for an
`is_authority_eligible` origin (`human`, `imported_curated`,
`legacy_unattributed`) -- never `agent_diagnostic` or omitted origin. Bird
Log, Dataset Export, classifier training manifests, and both analytics
paths below all key off `review_status`/`reviewed_label`, never off raw
`ReviewLabel` existence, so this one choke point is sufficient. The
frontend (`web/src/api/client.ts`) is the only caller that stamps
`review_origin: "human"`; no server-side default ever does.

## Observation / Today / Place Intelligence

- **Today in Your Yard**: `ProductRepository.dashboard_summary`
  (`product_repository.py`) feeds `web/src/pages/DashboardPage.tsx`
  directly -- no client-side re-aggregation of truth was found; the
  frontend renders backend-computed fields.
- **Zone Insights**: `analytics/zone_insights.py` -- deliberately
  **bird-only** per-Zone feeder metrics
  ([zone-feeder-insights-metrics.md](zone-feeder-insights-metrics.md)),
  rendered by `ZoneInsightsPanel.tsx`/`WildlifeInsightsPanel.tsx`. Narrower
  scope than Place Activity Report by design, not a stale duplicate of it.
- **Place Activity Report** (the Place Intelligence reporting foundation):
  `analytics/place_activity_report.py` (pure computation) +
  `place_activity_report_adapter.py` (typed-to-API adapter) +
  `ProductRepository.place_activity_report`, exposed read-only at `POST
  /api/analytics/place-activity-report`. Both this and `zone_insights` share
  the same canonical per-Visit truth resolver
  (`_stream_visit_summary_from_models` -> `_visit_review_outcome`), so
  confirmed-vs-provisional-vs-unresolved precedence cannot diverge between
  them. **Not yet surfaced in a dedicated frontend page** -- see "Next
  product action" at the end of this document.
- **Wildlife eligibility**: `wildlife_taxonomy.py::is_wildlife_category` is
  now the one shared "is this taxonomy category wildlife" predicate
  (a denylist, so a future category is wildlife by default). Used by
  `place_activity_report.py` and, as of this milestone, by
  `product_repository.py::_storage_visit_is_wildlife` (storage-retention's
  "protect reviewed wildlife" check) -- previously a second, independently
  hardcoded `{bird, mammal}` allowlist; see "Duplication consolidated"
  below. `zone_insights.py` intentionally stays bird-only and does not use
  this predicate.

## Production vs. research code boundary

**Entry points**

| Entry point | Role |
| --- | --- |
| `python -m mockingbird` (`runtime.py::main`) | The one production runtime: single FastAPI process, built frontend, local SQLite. |
| `python -m mockingbird --check` | Side-effect-light startup validation only. |
| `python -m mockingbird <subcommand>` (everything `__main__.py` dispatches besides the bare launch) | **Research/benchmark CLIs** -- `replay-benchmark`, `detector-benchmark`, `detector-comparison`, `multi-scale-benchmark`/`-comparison`, `motion-proposal-benchmark`/`-decision`, `temporal-capture`/`-mark`, `temporal-review-build`/`-validate`/`-export`, `stage3-tranche-review-build`, `burst-schedule-replay`, `evidence-benchmark`/`-comparison`, `candidate-authority-trial`. None of these run through the app; they are offline, shadow-only, or explicit Tier-4 trial tooling. |
| `python -m mockingbird_node` | The separate Camera Node edge-device package (`src/mockingbird_node/`) -- a different product component, not a duplicate entry point. |
| `systemctl start/stop/restart mockingbird-camera-node` | The supervised-service entry point onto the same package, installed by `scripts/install_camera_node.py`; runs the identical `python -m mockingbird_node` command as a dedicated unprivileged service account. See [camera-node-installer-design.md](camera-node-installer-design.md). |

**`observation/` package (58 files): production core vs. research/benchmark
harness.** Production (imported by `engine_runtime.py`, `camera_node_live.py`,
`api/main.py`, or `product_repository.py`): `engine_runtime.py`,
`camera_node_live.py`, `frame_driven_provider.py`, `frame_tracker.py`,
`reconnect_continuity.py`, `onnx_provider.py`, `mdv5_decoder.py`,
`burst_scheduler.py`, `localization_attribution.py`, `session_timeline.py`,
`media_contracts.py`, `visit_episode_assembler.py`, `evidence_scoring.py`,
`candidate_visit_adapter.py`, `candidate_visit_authority.py`,
`candidate_quality_gate.py`, `counterfactual_lineage.py`,
`unified_status.py`, `snapshot_provider.py`, `contracts.py`, `registry.py`.
Everything else in this package -- every `*_cli.py`, `*_benchmark*.py`,
`*_comparison*.py`, `replay*.py`, `temporal_*.py`, `motion_proposal_*.py`,
`multi_scale_*.py`, `detector_benchmark*.py`, `detector_comparison*.py`,
`detector_promotion.py`, `evidence_benchmark*.py`, `exact_frame_capture.py`,
`admission_policy.py`, `detection_quality_accounting.py`,
`evaluation_governance.py` -- is **research/benchmark tooling**: reachable
only from a CLI subcommand, a `scripts/*.py` entry point, or tests. These
share production types (`contracts.py`) and sometimes the production
detector (`onnx_provider.py`) deliberately, so a benchmark measures the real
thing -- that is shared infrastructure, not research code leaking into the
runtime.

**`training/` package and most of `scripts/`**: research. The wildlife
detector candidate-training pipeline (`training/wildlife*.py`,
`scripts/*_wildlife_*.py`, `scripts/train_wildlife_*.py`,
`scripts/evaluate_wildlife_*.py`, `scripts/materialize_wildlife_*.py`,
`scripts/build_wildlife_*.py`, `scripts/report_wildlife_*.py`,
`scripts/run_detector_candidate_benchmark.py`,
`scripts/run_detection_quality_accounting.py`) never runs from the product;
see [wildlife-detector-stage2-report.md](wildlife-detector-stage2-report.md)
for its current status (candidate model rejected on a real domain-gap
finding; production detector unchanged).

**Dev/ops tooling (KEEP, but not product runtime)**:
`scripts/build_local_product.py` (Windows packaging),
`scripts/deploy_windows_dev.py` (dev-box deployment, see
[windows-dev-deployment-design.md](windows-dev-deployment-design.md)),
`scripts/build_camera_node_artifact.py`, `scripts/install_camera_node.py`
(see [camera-node-installer-design.md](camera-node-installer-design.md)),
`scripts/prepare_bioclip_candidate_cache.py`,
`scripts/repair_review_label_provenance.py` (see
[review-decision-provenance-contract.md](review-decision-provenance-contract.md)),
`scripts/check_mvp_smoke.py`, `scripts/capture_zone_diagnostic.py`,
`scripts/run_local_image_smoke.py`, `scripts/evaluate_bioclip_field_truth.py`.

**Untracked, parked prototype (present on disk, deliberately never
integrated)**: `src/mockingbird/detectors/small_bird_benchmark.py`,
`scripts/evaluate_small_bird_detector.py`, `tests/test_small_bird_benchmark.py`
duplicate the already-accepted `observation/multi_scale_strategy.py`/
`multi_scale_benchmark.py` path and are hard-coupled to the legacy
`detectors/megadetector_adapter.py` shape. They are untracked by design (not
this milestone's to commit, integrate, or delete -- see "Code intentionally
retained" in the milestone report). A handful of `*.orig` files and a stray
`runtime_state.json` are other pre-existing untracked local artifacts,
likewise left exactly as found.

## Extension seams (where a new capability plugs in)

| Seam | Boundary doc | Entry point |
| --- | --- | --- |
| New Source/provider (camera, folder, webhook, ...) | [source-adapter-boundary-design.md](source-adapter-boundary-design.md) | `source_providers/`, registered underneath `Source`/`Stream` in `product_repository.py` |
| New detector/model adapter | [model-adapter-guardrails.md](model-adapter-guardrails.md), [model-selection.md](model-selection.md) | `detectors/` for the legacy per-image adapter shape; `observation/registry.py::ObservationEngineRegistry` for a new `ObservationProvider` in the accepted engine |
| New species classifier | [species-suggestion-adapter-design.md](species-suggestion-adapter-design.md) | `species/`, evidence-only by contract |
| Camera Node protocol | [camera-node-boundary-design.md](camera-node-boundary-design.md) | `source_providers/camera_node.py` (client, in the main app) and `src/mockingbird_node/` (the edge package itself) |
| New reporting fact | [place-activity-report-contract.md](place-activity-report-contract.md) | `analytics/`, reuse `_stream_visit_summary_from_models` rather than a new truth-precedence path |
| New environmental-context provider (sensor, weather API) | [environmental-context-foundation-v1-contract.md](environmental-context-foundation-v1-contract.md) | `environment/`, write to `environmental_context_records` with a new `provider_key`/`information_class` -- never a new table per provider |

## Where a contributor should start

| "I want to..." | Start here |
| --- | --- |
| Understand the whole system in 10 minutes | This document, then [architecture.md](architecture.md) |
| Change what counts as a reviewed truth write | `review_provenance.py`, then `ProductRepository._create_review_label_in_session` |
| Change Camera Node detection/tracking behavior | `observation/engine_runtime.py` and the pipeline list under "The accepted engine," above -- read [candidate-visit-authority-contract.md](candidate-visit-authority-contract.md) first |
| Change RTSP/USB/DirectShow motion behavior | `motion/scoring.py`, `motion/tracked_activity.py`, driven from `api/main.py` |
| Add a Dashboard/report fact | `analytics/place_activity_report.py` (or `zone_insights.py` for bird-only per-Zone metrics) -- never recompute truth precedence outside `_stream_visit_summary_from_models` |
| Add/adjust a species-suggestion input | `species/classifier_input.py::resolve_classifier_input` |
| Touch camera live-view/monitoring lifecycle | Read "Camera ownership," above, and [observation-engine-product-control-contract.md](observation-engine-product-control-contract.md), before editing `LiveCameraSessionManager` or `ObservationEngineSessionManager` |
| Add a Source/provider | [source-adapter-boundary-design.md](source-adapter-boundary-design.md), then `source_providers/` |
| Run a detector/model benchmark, not touch production | `observation/*_benchmark*.py`/`*_cli.py` via `python -m mockingbird <subcommand>` -- see [architecture.md](architecture.md) "Formal model lifecycle" |
| Understand what is safe to delete later | The classification inventory in this milestone's final report; when in doubt, treat anything reachable from `engine_runtime.py`, `unified_status.py`, `api/main.py`, or `product_repository.py` as KEEP |

## Frontend shape

`web/src/pages/` (26 pages), `web/src/components/` (31 components), one API
client (`web/src/api/client.ts`) and one types module
(`web/src/api/types.ts`) -- no second API client or duplicate type surface
was found. `ObservationControlPanel.tsx` is the single per-Stream
observation panel for every lane (see "Lane resolution," above); Stream
Detail no longer shows competing "Camera health"/"Monitoring continuity"
panels alongside it.

## Next product action

Place Activity Report has a complete, tested, read-only backend
(`POST /api/analytics/place-activity-report`) but no dedicated frontend
surface yet. That is the natural first slice of the upcoming Product
Experience / UI Cohesion work -- see the milestone report for the full
recommendation.
