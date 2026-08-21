"""App-owned lifecycle for the accepted Observation Engine.

Product requirement 1: a normal user must be able to start/stop the
accepted Observation Engine from MockingBird itself -- never
`candidate-authority-trial`, `temporal-capture`, or another CLI acceptance
tool. This module is the one seam that makes that possible: it reuses,
without modifying, every accepted Observation Engine v2 component --
`CameraNodeAnalysisSource`/`CameraNodeHttpTransport`/
`LiveCameraNodeShadowSession` (Stage 5), `FrameDrivenObservationProvider`/
`OnnxCudaObservationProvider` (Stage 3/4), `build_tracklets`/
`assemble_visit_episodes` (Stage 6.19), and `CandidateVisitAuthorityAdapter`
(Stage 7, itself now gated additionally by `candidate_quality_gate`) -- the
same construction `candidate_visit_authority_cli.py`'s bounded trial already
established, made long-running, app-owned, and cleanly stoppable instead of
hard-capped at 10 minutes / 3 candidates for an engineering trial.

Lifecycle model mirrors `mockingbird.playback.live_camera_session.
LiveCameraSessionManager`'s established convention: one bounded background
thread per Stream, explicit start/stop, side-effect-free status reads, and a
bounded join on stop. The one material difference is that the underlying
pipeline is itself `async`, so each session thread runs its own private
asyncio event loop rather than blocking network I/O directly on the caller.

"Start observing" is the one explicit user action that also turns on Stage
7's `candidate_visit` authority (`ProductRepository.
set_observation_authority_mode`, exactly the same call
`candidate-authority-trial --activate` already makes) -- shadow remains the
untouched schema/migration default; only this explicit action changes it.
"Stop observing" is this feature's kill switch: it always returns authority
to `shadow` before the session finishes stopping, so no candidate can ever
be created once a user has pressed Stop, regardless of what else is still
draining. Existing candidates are never touched by either action (see
"Existing Visit protection" in docs/candidate-visit-authority-contract.md).

Visit Continuity / Provisional Admission Fix v1 (see
docs/tracklet-visit-assembly-contract.md "Episode finality"): `_run_
assembly_tick` reruns the unmodified assembler over *every* track update
observed so far on every tick, so a proposal's own constituent tracklet set
-- and therefore its `proposal_id` -- can still grow on a later tick (a
same-encounter continuation tracklet finalizing after a brief gap). Each
tick supplies the latest source-relative offset this session has actually
observed (`known_horizon_ms`, advancing every analyzed frame regardless of
whether any track exists that frame) so the assembler itself can tell "this
proposal's tail boundary might still change" apart from "this proposal is
safe to offer for admission" -- never guessed here, never reconstructed
from tracker facts a second time. A proposal blocked only for that reason
(`blocked_continuation_pending`) is deliberately never marked permanently
attempted (see `RETRYABLE_OUTCOMES`), so it is naturally re-offered, either
under the same id once its boundary finalizes or under a new, larger id
once a continuation tracklet actually merges into it -- either way, one
coherent encounter still yields at most one candidate Visit. The session
-ending tick (`finalize=True`) treats every still-pending proposal as final
immediately: once the stream itself has ended, no continuation could ever
arrive, so nothing is left waiting forever.

Admission Recall Investigation + Conditional Fix v1 (see "Ambiguous
boundary arbitration" in docs/tracklet-visit-assembly-contract.md): a real
~94-minute accepted daily-use session found that `blocked_ambiguous_
boundary`, unlike `blocked_continuation_pending`, was a genuinely permanent
verdict with no recovery path at all -- including for a proposal with a
confirmed, above-strong-threshold detection, and for a well-evidenced,
cleanly-merged multi-generation episode that later absorbed more
continuation evidence without ever being reconsidered. `_run_assembly_tick`
now also calls `candidate_visit_authority.resolve_ambiguous_boundary_
arbitration` once per tick over the full freshly-assembled proposal set:
an ambiguous proposal whose own cluster (itself and every live sibling
named in `ambiguous_adjacent_proposal_ids`) has not yet stopped growing is
deferred (never attempted, exactly like `continuation_pending` already
behaves); once every member of a cluster has genuinely stopped growing,
the single best-evidenced member (by detector confidence, then evidence
volume, then a deterministic id tiebreak) is attempted with an explicit
`ambiguous_boundary_resolved=True` fact, letting it bypass the otherwise-
permanent block -- every other member of that same cluster is still
attempted normally and still blocks, so at most one Visit is ever admitted
per ambiguous cluster, exactly preserving the duplicate-Visit protection
the original policy existed to provide.
"""

from __future__ import annotations

import asyncio
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Callable, Protocol

from mockingbird.monitoring.exposure_history import exposure_close_reason_for_transition
from mockingbird.observation.acceptance_recorder import (
    AcceptanceRecorderConfig,
    BoundedFrameSampleRecorder,
)
from mockingbird.observation.camera_node_live import (
    CameraNodeAnalysisSource,
    CameraNodeHttpTransport,
    CameraNodeLiveTransport,
    LiveCameraNodeShadowSession,
)
from mockingbird.observation.candidate_quality_gate import REJECTED_OUTCOMES
from mockingbird.observation.candidate_visit_adapter import CandidateVisitAuthorityAdapter
from mockingbird.observation.candidate_visit_authority import (
    BLOCKED_OUTCOMES,
    RETRYABLE_OUTCOMES,
    ObservationAuthorityMode,
    resolve_ambiguous_boundary_arbitration,
)
from mockingbird.observation.contracts import (
    CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
    EvidenceCandidate,
    ObservationResult,
    TrackUpdate,
)
from mockingbird.observation.counterfactual_lineage import (
    BoundingBox,
    CounterfactualLedger,
    CounterfactualWindowResult,
)
from mockingbird.observation.frame_driven_provider import (
    FrameDrivenObservationProvider,
    FrameDrivenProviderConfiguration,
)
from mockingbird.observation.onnx_provider import OnnxCudaObservationProvider, OnnxModelBundle
from mockingbird.observation.visit_episode_assembler import assemble_visit_episodes, build_tracklets
from mockingbird.repository.product_repository import ProductRepository, StreamLivePlaybackConfig
from mockingbird.source_providers.camera_node import CameraNodeClient, CameraNodeClientError
from mockingbird.species.automatic_identification import AutomaticReviewIdentificationAssist
from mockingbird.motion.high_resolution_evidence import AlignmentDecision, CaptureProfileGeometry, resolve_alignment
from mockingbird.web_app import find_workspace_root

PROVIDER_CONFIG_PATH_ENV = "MOCKINGBIRD_OBSERVATION_PROVIDER_CONFIG_PATH"
# Historical developer/CLI convention (README.md, replay-benchmark,
# candidate-authority-trial): a path *relative to a development checkout's
# root*, never to process cwd -- see `resolve_provider_config_path`.
DEFAULT_PROVIDER_CONFIG_PATH = Path("data/models/observation-frame-driven/provider-config.json")
PACKAGED_OBSERVATION_RUNTIME_DIRNAME = "observation_runtime"
PACKAGED_PROVIDER_CONFIG_FILENAME = "provider-config.json"

_BATCH_FRAMES = 20
_ASSEMBLY_TICK_SECONDS = 10.0
_STOP_JOIN_TIMEOUT_SECONDS = 20.0
_MAX_SUPPRESSED_REASONS = 8

ObservationEngineState = str  # "stopped" | "starting" | "observing" | "stopping" | "error"


class _DetectorProvenance(Protocol):
    provider_id: str


ProviderLoader = Callable[[Path], tuple[FrameDrivenObservationProvider, _DetectorProvenance]]
TransportFactory = Callable[[StreamLivePlaybackConfig, str], CameraNodeLiveTransport]
# End-to-End Bird Encounter Recall Closure v1: lets a caller (in practice
# only `main.get_observation_engine_session_manager`, via `acceptance_
# recorder.acceptance_recorder_config_from_env`) tune one opted-in field
# session's recorder bounds without this module knowing anything about env
# vars itself -- mirrors `ProviderLoader`/`TransportFactory`'s own
# injected-factory shape exactly.
AcceptanceRecorderConfigFactory = Callable[[Path], AcceptanceRecorderConfig]


class LiveCameraSessionCoordinator(Protocol):
    """The narrow slice of `mockingbird.playback.live_camera_session.
    LiveCameraSessionManager` this module needs so Observation Engine never
    unknowingly competes with the existing legacy live-view/monitoring
    camera session for the same physical Camera Node camera. Both methods
    are already idempotent/self-checking on the manager side: pausing when
    nothing is running, or resuming a session this class did not itself
    pause, is always a safe no-op there -- never re-implemented here."""

    def pause_for_observation(self, stream_id: str) -> object | None: ...
    def resume_after_observation(self, config: StreamLivePlaybackConfig) -> object | None: ...


def _load_real_provider(provider_config_path: Path) -> tuple[FrameDrivenObservationProvider, OnnxCudaObservationProvider]:
    """The real, accepted Observation Engine provider construction --
    identical to `candidate_visit_authority_cli.py`'s own. Isolated into one
    function so tests can inject a fake provider/detector instead without
    CUDA hardware, while production always takes this exact path."""

    configuration = FrameDrivenProviderConfiguration.load(provider_config_path)
    bundle = OnnxModelBundle.load(configuration.model_bundle_path)
    detector = OnnxCudaObservationProvider(bundle=bundle)
    provider = FrameDrivenObservationProvider(detector=detector, settings=configuration.settings)
    provider.load()
    return provider, detector


def _default_transport_factory(config: StreamLivePlaybackConfig, stream_id: str) -> CameraNodeHttpTransport:
    return CameraNodeHttpTransport(
        base_address=config.camera_node_base_address,
        credential=config.camera_node_credential,
        camera_id=config.camera_node_camera_id,
        stream_id=stream_id,
        evidence_profile_id=config.camera_node_evidence_profile_id,
    )


CaptureProfileAlignmentFactory = Callable[[StreamLivePlaybackConfig], AlignmentDecision | None]


def _default_capture_profile_alignment(
    config: StreamLivePlaybackConfig,
) -> AlignmentDecision | None:
    """Fetch this Stream's real monitoring/evidence capture-profile geometry
    once, at session start, and honestly resolve whether they are FOV-
    aligned (Source-Resolution + Multi-Frame Species Evidence v1) -- never
    per-frame, never guessed from normalized-coordinate reuse alone. Mirrors
    `api.main._high_resolution_capture_claim_profile_lineage`'s identical
    fetch-and-build shape for the legacy live-view capture path (a small,
    obviously-correct duplication of six field mappings rather than a
    reverse `api` -> `observation` import).

    Returns `None` -- never raises -- for any incomplete configuration,
    network failure, or missing/unsupported profile: alignment is an
    optional, additive upgrade to resolution provenance, and a Camera Node
    that is temporarily unreachable at session start must never block
    Observation Engine startup or degrade to anything other than today's
    unchanged `near_time_capture`/`fallback` behavior (see "Camera/provider
    failure behavior" in
    docs/source-resolution-multi-frame-species-evidence-contract.md).
    """

    if (
        config.provider_key != "camera_node"
        or not config.camera_node_base_address
        or not config.camera_node_credential
        or not config.camera_node_camera_id
        or not config.camera_node_monitoring_profile_id
        or not config.camera_node_evidence_profile_id
    ):
        return None
    try:
        camera = next(
            (
                item
                for item in CameraNodeClient().cameras(
                    base_address=config.camera_node_base_address,
                    credential=config.camera_node_credential,
                )
                if item.camera_id == config.camera_node_camera_id
            ),
            None,
        )
        if camera is None:
            return None
        profiles_by_id = {profile.profile_id: profile for profile in camera.capture_profiles}
        monitoring = profiles_by_id.get(config.camera_node_monitoring_profile_id)
        evidence = profiles_by_id.get(config.camera_node_evidence_profile_id)
        if (
            monitoring is None
            or evidence is None
            or not monitoring.supports_monitoring
            or not evidence.supports_evidence
        ):
            return None
        return resolve_alignment(
            CaptureProfileGeometry(
                profile_id=monitoring.profile_id,
                width=monitoring.width,
                height=monitoring.height,
                geometry_group=monitoring.geometry_group,
                orientation=monitoring.orientation,
                mirrored=monitoring.mirrored,
                same_fov=monitoring.same_fov,
            ),
            CaptureProfileGeometry(
                profile_id=evidence.profile_id,
                width=evidence.width,
                height=evidence.height,
                geometry_group=evidence.geometry_group,
                orientation=evidence.orientation,
                mirrored=evidence.mirrored,
                same_fov=evidence.same_fov,
            ),
        )
    except CameraNodeClientError:
        return None


def packaged_observation_runtime_root() -> Path:
    """Where a packaged MockingBird install ships its default Observation
    Engine provider configuration and model bundle -- populated by
    `scripts/build_local_product.py`, mirroring `web_app.
    resolve_frontend_dist`'s own "packaged asset next to this installed
    package" convention exactly (`web_dist` there, `observation_runtime`
    here: both live at the installed `mockingbird` package's own root,
    sibling to this `observation/` package). Resolved from *this module's
    own installed location*, never from `os.getcwd()`, so it keeps
    resolving correctly after `runtime.py`'s `run_preflight()` changes the
    process working directory to the runtime home, and after restarting
    MockingBird from any other working directory."""

    return Path(__file__).resolve().parent.parent / PACKAGED_OBSERVATION_RUNTIME_DIRNAME


def resolve_provider_config_path(override: Path | None = None) -> Path:
    """Packaged-runtime configuration resolution order (a normal packaged
    install never needs `MOCKINGBIRD_OBSERVATION_PROVIDER_CONFIG_PATH` set):

    1. an explicit caller-supplied override (tests, a future setup flow);
    2. the explicit advanced/developer environment override -- still
       honored, for a developer or advanced user who wants a different
       bundle than the one that shipped, but never required;
    3. the packaged production provider configuration next to this
       installed package (`build_local_product.py` places one there --
       see `packaged_observation_runtime_root`);
    4. the historical development-checkout convention
       (`data/models/observation-frame-driven/provider-config.json`),
       resolved against the discovered workspace root (`find_workspace_root`,
       the same helper `runtime.py` already uses) rather than
       `os.getcwd()`, so a developer checkout keeps working regardless of
       which directory MockingBird was started from;
    5. if none of the above exist, the packaged-root candidate path is
       still returned -- never raises here. `FrameDrivenProviderConfiguration
       .load` reports one honest, specific "missing" failure rather than
       this function guessing or silently picking a wrong path.
    """

    if override is not None:
        return override
    configured = os.environ.get(PROVIDER_CONFIG_PATH_ENV)
    if configured:
        return Path(configured)
    packaged_candidate = packaged_observation_runtime_root() / PACKAGED_PROVIDER_CONFIG_FILENAME
    if packaged_candidate.is_file():
        return packaged_candidate
    workspace_root = find_workspace_root()
    if workspace_root is not None:
        return workspace_root / DEFAULT_PROVIDER_CONFIG_PATH
    return packaged_candidate


@dataclass(frozen=True)
class ObservationEngineCounts:
    track_updates_observed: int = 0
    evidence_candidates_observed: int = 0
    proposals_observed: int = 0
    candidates_created: int = 0
    candidates_suppressed: int = 0
    # Bounded (reason, count) pairs, most frequent first -- the "useful
    # diagnostic counts for suppressed proposals" product requirement 7
    # asks for, without a durable schema change: this is transient,
    # per-running-session diagnostic state, not dataset truth.
    suppressed_reasons: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True)
class ObservationEngineSessionStatus:
    stream_id: str
    state: ObservationEngineState
    observing: bool
    message: str
    camera_connected: bool
    camera_message: str
    engine_available: bool
    engine_message: str
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    stopped_reason: str | None = None
    last_candidate_visit_id: str | None = None
    # Visit Authority Budget + Ambiguous-Boundary Recall Closure v1: truthful,
    # plain-language-adjacent health facts distinct from `message`/
    # `engine_message` (which stay reserved for camera/engine subsystem
    # problems, per the existing "headline whichever subsystem is actually
    # blocking" convention) -- this session can be genuinely `observing` and
    # `engine_available` while still unable to create any further Visit.
    # `False`/`None` for every session that has never hit this. See
    # docs/candidate-visit-authority-contract.md "Health/diagnostic truth
    # for budget exhaustion."
    candidate_authority_exhausted: bool = False
    candidate_authority_message: str | None = None
    counts: ObservationEngineCounts = field(default_factory=ObservationEngineCounts)
    advanced: dict[str, object] = field(default_factory=dict)


def _sanitized(error: BaseException) -> str:
    """Never let a raw exception message (which can carry a local path or
    transport detail) reach product status; every error this module raises
    itself is already a short stable code, so this is a bounded fallback for
    a genuinely unexpected third-party exception."""

    text = str(error) or error.__class__.__name__
    return text[:200]


# The bounded, already-honest error codes `FrameDrivenProviderConfiguration
# .load`/`OnnxModelBundle.load` (missing/invalid provider config or model
# bundle, corrupt file, fingerprint mismatch) and `OnnxCudaObservationProvider
# .load` (missing/unsupported CUDA execution provider) already raise --
# classified here into the two plain-language product categories the "Camera
# health/status correction" contract asks for, so a normal user sees *which*
# subsystem is actually broken instead of one generic sentence. Never widens
# or invents a new failure mode: every code below is already produced
# upstream unchanged.
_MISSING_MODEL_OR_RUNTIME_CODES = frozenset({
    "invalid_frame_driven_configuration",
    "invalid_frame_driven_settings",
    "invalid_model_bundle_path",
    "invalid_model_bundle_json",
    "unsupported_model_bundle_version",
    "invalid_model_path",
    "unsupported_model_format",
    "unsupported_decoder",
    "invalid_model_bundle",
    "model_fingerprint_mismatch",
    "provider_configuration_required",
    "provider_already_loaded",
})
_UNSUPPORTED_GPU_CODES = frozenset({
    "onnx_cuda_unavailable",
    "onnx_cuda_no_fallback",
    "onnx_cuda_session_load_failed",
    "onnx_cuda_mixed_execution",
    "onnx_cuda_verification_insufficient",
})


@dataclass(frozen=True)
class AnalysisStreamRetryPolicy:
    """Bounded retry policy for one *recoverable* interruption of the live
    Camera Node analysis-stream transport (`session.run()` in `_run_async`
    below) -- Observation Engine Session-Renewal Continuity v1 (see
    docs/observation-session-renewal-continuity-contract.md).

    Distinct from `reconnect_continuity.ReconnectBridgeConfig`: that module
    bridges one still-active *track* across a benign transport reconnect it
    already sees fresh frames for. This policy instead bounds how long this
    session keeps re-attempting `session.run()` itself while frames are not
    arriving at all -- a `CameraNodeClientError`/`ValueError`, or a batch
    that completes with zero frames, are both already-observed, honest
    shapes of "the Camera Node's own physical-camera-lock contention
    outlasted one bounded ~10-second analysis-stream batch" (see
    `mockingbird_node.app.analysis_parts`, which already tolerates this
    exact shape server-side -- its own
    `test_analysis_stream_ends_cleanly_when_camera_never_recovers` docstring
    says so explicitly: "so the client's existing reconnect logic can take
    over"). A track/Visit-in-progress is never touched while this policy is
    retrying -- `all_track_updates`/`all_evidence_candidates`/the live
    `provider`'s own tracker generation all simply keep accumulating exactly
    as they would across any ordinary reconnect, so a successful resume
    resumes the same encounter rather than starting a new one.

    Exhausting this bounded budget without a single successful frame still
    ends the session exactly as before this fix
    (`stopped_reason="camera_unavailable"`) -- this never retries forever.
    """

    #: How many consecutive recoverable `session.run()` outcomes (raised or
    #: empty) this session tolerates in a row before giving up and treating
    #: the interruption as genuinely terminal -- "persistent provider
    #: failure after bounded recovery" in the contract doc's classification.
    maximum_consecutive_failures: int = 6
    #: Bounded, interruptible pause between consecutive retry attempts --
    #: never a busy loop hammering the Node, and always cut short the
    #: instant an explicit Stop is requested (see `_await_transport_retry`).
    #:
    #: This default was raised from 2.0 to 12.0 after Camera Node Installer
    #: v1's real reboot-recovery experiment measured a genuine premature
    #: give-up: a fully unreachable Node (the real shape of a device
    #: rebooting, not a merely-degraded one) fails each `session.run()`
    #: attempt in roughly a second rather than after a full ~10s batch
    #: timeout -- the batch-duration case this budget was originally,
    #: implicitly modeled on. At the old 2.0s value the six-attempt budget
    #: was exhausted in a measured ~20s of real wall-clock retrying (total
    #: session time to give-up ~38s from the interruption), while the same
    #: real Raspberry Pi 4 needed a measured ~55s to become healthy again
    #: after a normal reboot -- the host gave up about 17s before a
    #: perfectly healthy Node could have reconnected. 12.0s keeps
    #: `maximum_consecutive_failures` and the overall bounded-retry shape
    #: unchanged (never infinite) while restoring the "~70-90 second"
    #: budget this module's own docs already documented as the design
    #: intent (see docs/observation-session-renewal-continuity-contract.md
    #: and docs/camera-node-installer-design.md "Real hardware acceptance
    #: findings" for the exact measurement and the re-validated reboot run
    #: this fix required).
    backoff_seconds: float = 12.0

    def __post_init__(self) -> None:
        if not 1 <= self.maximum_consecutive_failures <= 30 or not 0.0 <= self.backoff_seconds <= 60.0:
            raise ValueError("invalid_analysis_stream_retry_policy")


# `session.run()`'s real call chain (`CameraNodeHttpTransport.
# iter_analysis_frames`) can only ever raise these two `CameraNodeClientError`
# codes for a reason retrying can never fix: the paired credential itself was
# rejected, or the configured address stopped behaving like this Camera
# Node's own paired endpoint at all (a redirect). Both match this contract's
# "node identity/pairing invalid" terminal category exactly -- retrying
# either only delays an honest terminal status the user needs to act on
# (re-pair). Every other code this call chain can raise
# (`analysis_stream_unavailable`, `analysis_stream_invalid`), a bare
# `ValueError`, or any future code, is treated as bounded-recoverable -- see
# `AnalysisStreamRetryPolicy`. Deliberately not the same set as
# `_MISSING_MODEL_OR_RUNTIME_CODES`/`_UNSUPPORTED_GPU_CODES` above (those
# classify a *Start*-time engine-load failure) or
# `CAMERA_NODE_RUNTIME_FAILURE_CODES` (that one classifies a *different*
# subsystem's snapshot/capture failures for its own UI-health purpose) --
# this set answers one narrow question: should the live analysis-stream loop
# keep retrying `session.run()`?
_TERMINAL_ANALYSIS_STREAM_ERROR_CODES = frozenset({
    "authentication_rejected",
    "node_redirect_rejected",
})


def _engine_failure_message(error: BaseException) -> tuple[str, str]:
    """Return `(basic_message, category)` for an Observation Engine start
    failure. `basic_message` never tells a normal user to set an
    environment variable or otherwise touch packaging internals -- the
    product requirement is that a normal packaged install never requires
    that. The short stable error code stays visible in parentheses (already
    the existing convention here) for advanced diagnostics/support, and
    `category` is recorded separately in `advanced` rather than folded into
    the basic sentence."""

    code = _sanitized(error)
    if code in _MISSING_MODEL_OR_RUNTIME_CODES:
        return (
            f"The Observation Engine's model bundle is missing or invalid. "
            f"Reinstalling MockingBird usually fixes this. ({code})",
            "missing_model_or_runtime",
        )
    if code in _UNSUPPORTED_GPU_CODES:
        return (
            f"This PC's GPU/graphics driver does not meet Observation Engine "
            f"requirements (a compatible NVIDIA GPU and driver are required). ({code})",
            "unsupported_gpu",
        )
    return (f"The Observation Engine could not start. ({code})", "failed")


class _EngineSession:
    """One Stream's bounded background observation loop and its snapshot-
    able status. All mutable state is behind `_state_lock`; the network/GPU
    work itself runs entirely on `_thread`, never on a caller's thread."""

    def __init__(
        self,
        *,
        stream_id: str,
        playback_config: StreamLivePlaybackConfig,
        provider_config_path: Path,
        privacy_ignore_regions: tuple[tuple[float, float, float, float], ...],
        repository_factory: Callable[[], ProductRepository],
        provider_loader: ProviderLoader = _load_real_provider,
        transport_factory: TransportFactory = _default_transport_factory,
        capture_profile_alignment_factory: CaptureProfileAlignmentFactory = _default_capture_profile_alignment,
        live_camera_sessions: LiveCameraSessionCoordinator | None = None,
        automatic_identification_assist: AutomaticReviewIdentificationAssist | None = None,
        analysis_stream_retry_policy: AnalysisStreamRetryPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        acceptance_recorder: BoundedFrameSampleRecorder | None = None,
    ) -> None:
        self.stream_id = stream_id
        self._playback_config = playback_config
        self._provider_config_path = provider_config_path
        self._privacy_ignore_regions = privacy_ignore_regions
        self._repository_factory = repository_factory
        self._provider_loader = provider_loader
        self._transport_factory = transport_factory
        self._capture_profile_alignment_factory = capture_profile_alignment_factory
        self._live_camera_sessions = live_camera_sessions
        self._automatic_identification_assist = automatic_identification_assist
        self._retry_policy = analysis_stream_retry_policy or AnalysisStreamRetryPolicy()
        # Independent biological-encounter denominator (Visit Authority
        # Budget + Ambiguous-Boundary Recall Closure v1): `None` unless a
        # caller explicitly supplies one -- off by default for every normal
        # product Start, matching "do not create a large recording
        # subsystem." See docs/independent-encounter-denominator-design.md.
        self._acceptance_recorder = acceptance_recorder
        # Today Coverage Truth v1: injectable only for tests (mirrors
        # `DurableMonitoringSupervisor`'s own `clock` parameter, the
        # existing convention for deterministically testing bounded-cadence
        # durable-exposure checkpointing without a real wall-clock wait);
        # production always takes the default real clock.
        self._clock: Callable[[], datetime] = clock or (lambda: datetime.now(UTC))
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_lock = threading.RLock()
        self._state: ObservationEngineState = "starting"
        self._started_at: datetime | None = None
        self._stopped_at: datetime | None = None
        self._stopped_reason: str | None = None
        # Today Coverage Truth v1 (see docs/todays-coverage-truth-contract.md):
        # one stable id for this session's entire run, mirroring the legacy
        # durable-monitoring-supervisor's own `runtime_generation_id`
        # convention -- a fresh `_EngineSession` object is constructed on
        # every "Start observing" (`ObservationEngineSessionManager.start`),
        # so a new generation id here always correctly rotates past (and
        # closes) any interval a prior, now-abandoned session left open.
        # `_last_healthy_frame_at` is the best in-memory known-good frame
        # time -- finer-grained than the durable checkpoint's own bounded
        # cadence -- supplied to the exposure closer on the way out so a
        # clean Stop closes at the true observed boundary, not one
        # artificially truncated to the last persisted checkpoint.
        self._runtime_generation_id = uuid.uuid4().hex
        self._last_healthy_frame_at: datetime | None = None
        self._camera_connected = False
        self._camera_message = "Connecting to the Camera Node…"
        self._engine_available = False
        self._engine_message = "Observation Engine has not started yet."
        self._counts = ObservationEngineCounts()
        self._suppressed: dict[str, int] = {}
        # Harvested Evidence Issuance / Missing-Evidence Closure v1: a
        # bounded lifetime counter of every already-captured burst/same-
        # frame candidate whose content hash was no longer found in the
        # live session's own small temporary cache at harvest time -- by
        # construction, always a genuine "captured, then lost before
        # harvest" fact, never "never captured" (see `_harvest_burst_bytes`/
        # `_harvest_same_frame_bytes`'s own return-value docstring). Before
        # this milestone, nothing distinguished this from "the burst
        # scheduler never issued a request" after the fact -- see docs/
        # cache-128-live-daylight-acceptance-v1-report.md §7's own disclosed
        # "no surviving log/API signal" limitation. A non-zero value here in
        # a future session is a direct, immediate signal that this exact
        # category is recurring, without needing another forensic
        # reconstruction from the counterfactual ledger.
        self._evidence_harvest_misses = 0
        self._last_candidate_visit_id: str | None = None
        # Visit Authority Budget + Ambiguous-Boundary Recall Closure v1: a
        # candidate budget legitimately running out mid-session must be
        # truthfully surfaced, not silently absorbed into the generic
        # suppressed-reasons diagnostic alone (see "Health/diagnostic truth
        # for budget exhaustion" in docs/candidate-visit-authority-
        # contract.md). Sticky for the lifetime of this running session,
        # matching `blocked_session_limit`'s own permanent-for-this-
        # activation-window semantics (`candidate_visit_authority.
        # RETRYABLE_OUTCOMES` excludes it) -- once true, stays true until
        # this session stops (a fresh Start gets a fresh activation boundary
        # and therefore a fresh flag).
        self._candidate_authority_exhausted = False
        self._candidate_authority_message: str | None = None
        self._advanced: dict[str, object] = {}
        # Rejected / Suppressed Detection Attribution v1 (see
        # docs/rejected-detection-attribution-contract.md): one bounded,
        # local-only counterfactual ledger per session, created fresh here
        # so a new Start can never mix its own records with a prior,
        # already-stopped session's (see "session reset/restart" in the
        # contract doc). `_suppressed` above is left unmodified/unremoved --
        # this ledger is an addition, not a replacement.
        self._counterfactual = CounterfactualLedger(stream_id=stream_id)

    @property
    def is_active(self) -> bool:
        with self._state_lock:
            return self._state in {"starting", "observing", "stopping"}

    def start(self) -> None:
        self._started_at = datetime.now(UTC)
        self._thread = threading.Thread(
            target=self._run, name=f"observation-engine:{self.stream_id}", daemon=True,
        )
        self._thread.start()

    def stop(self, *, reason: str = "user_stopped") -> None:
        with self._state_lock:
            if self._state == "stopped":
                return
            self._state = "stopping"
            self._stopped_reason = reason
        self._stop_event.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=_STOP_JOIN_TIMEOUT_SECONDS)
        # The kill switch: always return authority to shadow on the way out,
        # even if the background thread failed to join cleanly in time, so
        # a stuck thread can never leave candidate authority active.
        try:
            repository = self._repository_factory()
            try:
                repository.set_observation_authority_mode(
                    ObservationAuthorityMode.shadow, stream_id=self.stream_id,
                )
            finally:
                repository.close()
        except Exception:  # pragma: no cover - defensive: stop must never raise
            pass
        with self._state_lock:
            self._state = "stopped"
            self._stopped_at = datetime.now(UTC)

    def snapshot(self) -> ObservationEngineSessionStatus:
        with self._state_lock:
            observing = self._state == "observing"
            message = {
                "starting": "Connecting to the Camera Node and loading the Observation Engine…",
                "observing": "MockingBird is watching this camera for wildlife.",
                "stopping": "Stopping observation…",
                "stopped": "Not observing.",
                # Headline whichever subsystem is actually the blocking
                # problem: an unpaired/unreachable camera is reported via
                # its own specific `camera_message` (never a generic engine
                # placeholder); once the camera is configured, a later
                # Observation Engine failure (missing model, unsupported
                # GPU) is reported via its own specific `engine_message` --
                # never the other way around, which is exactly the
                # contradiction the "Camera health/status correction"
                # contract exists to fix.
                "error": self._camera_message if not self._camera_connected else self._engine_message,
            }[self._state]
            suppressed_reasons = tuple(
                sorted(self._suppressed.items(), key=lambda item: (-item[1], item[0]))[:_MAX_SUPPRESSED_REASONS]
            )
            counts = ObservationEngineCounts(
                track_updates_observed=self._counts.track_updates_observed,
                evidence_candidates_observed=self._counts.evidence_candidates_observed,
                proposals_observed=self._counts.proposals_observed,
                candidates_created=self._counts.candidates_created,
                candidates_suppressed=self._counts.candidates_suppressed,
                suppressed_reasons=suppressed_reasons,
            )
            advanced = dict(self._advanced)
            advanced["counterfactual_ledger"] = self._counterfactual_summary()
            # Harvested Evidence Issuance / Missing-Evidence Closure v1: see
            # `self._evidence_harvest_misses`'s own docstring at assignment.
            advanced["evidence_harvest_misses"] = self._evidence_harvest_misses
            # Camera Node Connectivity & Recovery Diagnosis v1: the best
            # in-memory known-good frame time (see `_checkpoint_observation_
            # exposure`), so a caller diagnosing a stalled/degraded session
            # can see "last real frame N minutes ago" without cross-
            # referencing the durable exposure-interval table separately.
            advanced["last_healthy_frame_at"] = (
                self._last_healthy_frame_at.isoformat() if self._last_healthy_frame_at else None
            )
            return ObservationEngineSessionStatus(
                stream_id=self.stream_id,
                state=self._state,
                observing=observing,
                message=message,
                camera_connected=self._camera_connected,
                camera_message=self._camera_message,
                engine_available=self._engine_available,
                engine_message=self._engine_message,
                started_at=self._started_at,
                stopped_at=self._stopped_at,
                stopped_reason=self._stopped_reason,
                last_candidate_visit_id=self._last_candidate_visit_id,
                candidate_authority_exhausted=self._candidate_authority_exhausted,
                candidate_authority_message=self._candidate_authority_message,
                counts=counts,
                advanced=advanced,
            )

    def _counterfactual_summary(self) -> dict[str, object]:
        """Bounded, JSON-safe eviction/coverage summary for the existing
        advanced-diagnostics surface (Rejected / Suppressed Detection
        Attribution v1) -- an operator can see at a glance whether older
        counterfactual evidence has already been evicted, without needing
        the full ROI/time-window query surface (`counterfactual_query`)."""

        coverage = self._counterfactual.coverage()

        def _accounting(accounting) -> dict[str, object]:
            return {
                "retained_count": accounting.retained_count,
                "evicted_count": accounting.evicted_count,
                "recorded_count": accounting.recorded_count,
                "oldest_retained_offset_ms": accounting.oldest_retained_offset_ms,
                "newest_retained_offset_ms": accounting.newest_retained_offset_ms,
            }

        return {
            "session_first_offset_ms": coverage.session_first_offset_ms,
            "session_last_offset_ms": coverage.session_last_offset_ms,
            "raw_detections": _accounting(coverage.raw_detection_retention),
            "track_generations": _accounting(coverage.track_generation_retention),
            "proposal_outcomes": _accounting(coverage.proposal_outcome_retention),
        }

    def counterfactual_query(
        self, *, start_offset_ms: int, end_offset_ms: int, roi: BoundingBox | None = None,
    ) -> CounterfactualWindowResult:
        """Side-effect-free bounded read into this session's own
        counterfactual ledger -- see docs/rejected-detection-attribution
        -contract.md. Safe to call while `_run_async` is still actively
        mutating the ledger from a different thread (the ledger is
        internally locked, mirroring `_state_lock`'s own role for every
        other cross-thread status read on this class)."""

        return self._counterfactual.query(start_offset_ms=start_offset_ms, end_offset_ms=end_offset_ms, roi=roi)

    def _run(self) -> None:
        try:
            asyncio.run(self._run_async())
        except Exception as error:  # pragma: no cover - defensive: never crash the app process
            with self._state_lock:
                self._state = "error"
                self._camera_message = _sanitized(error)
        finally:
            with self._state_lock:
                # "error" is already a terminal, non-active state (see
                # `is_active`) recorded with its own honest reason; only a
                # still in-flight state (the loop ended on its own -- stream
                # end or an explicit Stop) is normalized to "stopped" here.
                if self._state in {"starting", "observing", "stopping"}:
                    self._state = "stopped"
                    self._stopped_at = self._stopped_at or datetime.now(UTC)
                    self._stopped_reason = self._stopped_reason or "session_ended"

    async def _run_async(self) -> None:
        config = self._playback_config
        if (
            config.provider_key != "camera_node"
            or not config.camera_node_base_address
            or not config.camera_node_credential
            or not config.camera_node_camera_id
            or not config.camera_node_evidence_profile_id
        ):
            with self._state_lock:
                self._state = "error"
                self._camera_connected = False
                self._camera_message = (
                    "This camera isn't a paired MockingBird Camera Node yet. Pair a Camera Node "
                    "in Add Camera to use Observation Engine wildlife detection here."
                )
            return

        # Pairing configuration is already fully validated above -- report
        # the Camera Node as configured now, *before* attempting the
        # potentially slow, GPU-heavy Observation Engine load below. This is
        # what the "Camera health/status correction" contract requires: a
        # later engine-load failure (missing model, unsupported GPU) must
        # never leave a stale "not yet connected" camera fact sitting next
        # to an unrelated Observation runtime problem. A genuine transport
        # failure once frames are actually requested still revises this
        # back down (see the `CameraNodeClientError` handling below).
        with self._state_lock:
            self._camera_connected = True
            self._camera_message = "Camera Node is paired and configured."

        load_started = perf_counter()
        try:
            provider, detector = self._provider_loader(self._provider_config_path)
        except (ValueError, OSError, RuntimeError) as error:
            basic_message, category = _engine_failure_message(error)
            with self._state_lock:
                self._state = "error"
                self._engine_available = False
                self._engine_message = basic_message
                self._advanced["engine_error_category"] = category
                self._advanced["engine_error_code"] = _sanitized(error)
                self._advanced["provider_config_path"] = str(self._provider_config_path)
                self._advanced["provider_config_env_var"] = PROVIDER_CONFIG_PATH_ENV
                self._advanced["engine_load_duration_ms"] = round((perf_counter() - load_started) * 1000, 1)
            return

        with self._state_lock:
            self._engine_available = True
            self._engine_message = "Observation Engine is running."
            self._advanced["provider_key"] = provider.provider_id
            self._advanced["detector_provider_key"] = getattr(detector, "provider_id", "onnx-cuda")
            self._advanced["engine_load_duration_ms"] = round((perf_counter() - load_started) * 1000, 1)
            # GPU/execution-provider/model-bundle-version facts for the
            # collapsed advanced-diagnostics disclosure only (never the
            # basic UI) -- whatever the real detector already computes in
            # `report_metadata`, untouched; a fixture detector without one
            # (existing hardware-free tests) is simply omitted, not an error.
            report_metadata = getattr(detector, "report_metadata", None)
            if callable(report_metadata):
                try:
                    self._advanced["model_runtime_metadata"] = report_metadata()
                except Exception:  # pragma: no cover - diagnostics must never break Start
                    pass

        repository = self._repository_factory()
        try:
            # `fresh_session=True`: this call happens exactly once per real
            # "Start observing" action (a brand-new `_EngineSession`, only
            # ever constructed when no session for this Stream is already
            # active -- see `ObservationEngineSessionManager.start`), so it
            # always establishes a fresh candidate-authority activation
            # boundary for *this Stream*, even if a prior process crash or
            # redeploy left this Stream's own persisted mode stuck at
            # `candidate_visit` without ever reaching `stop()`'s kill switch.
            # See "Fresh-session activation" in
            # docs/candidate-visit-authority-contract.md.
            activation = repository.set_observation_authority_mode(
                ObservationAuthorityMode.candidate_visit, stream_id=self.stream_id, fresh_session=True,
            )
            with self._state_lock:
                self._advanced["activation_boundary_at"] = (
                    activation.activation_boundary_at.isoformat()
                    if activation.activation_boundary_at
                    else None
                )

            source = CameraNodeAnalysisSource(
                self.stream_id, analysis_excluded_regions=self._privacy_ignore_regions,
            )
            transport = self._transport_factory(config, self.stream_id)
            # Source-Resolution + Multi-Frame Species Evidence v1: resolved
            # once here (a bounded, already-timeout-protected Camera Node
            # metadata call, mirroring the pairing/health checks this same
            # startup path already performs) -- never per-frame. `None` on
            # any failure/incomplete configuration; the session degrades to
            # exactly its pre-milestone behavior in that case, never blocked.
            resolution_alignment = self._capture_profile_alignment_factory(config)
            with self._state_lock:
                self._advanced["resolution_alignment_status"] = (
                    resolution_alignment.status if resolution_alignment is not None else "not_checked"
                )
            session = LiveCameraNodeShadowSession(
                source=source, transport=transport, provider=provider,
                evidence_profile_id=config.camera_node_evidence_profile_id,
                resolution_alignment=resolution_alignment,
            )
            adapter = CandidateVisitAuthorityAdapter(
                repository, detector_provenance=detector.provider_id, tracker_provenance=provider.provider_id,
                provider_key=provider.provider_id,
            )

            all_track_updates: list[TrackUpdate] = []
            all_evidence_candidates: list[EvidenceCandidate] = []
            attempted_proposal_ids: set[str] = set()
            # The latest source-relative offset (ms) this session has
            # actually processed so far -- advances on every analyzed frame
            # (`ObservationResult.frame_packets`, always populated) whether
            # or not that frame carried a track, so a genuinely quiet period
            # still lets a pending episode's continuation window eventually
            # close (see `_run_assembly_tick`'s `known_horizon_ms`). Never a
            # wall-clock read itself -- this stays a source-relative fact,
            # matching every offset the assembler already reasons about.
            latest_known_offset_ms = 0
            # A track only becomes an assemble-able, terminal `Tracklet` once
            # its generation actually ends -- which, for a proposal only
            # completed by the stream's natural end, happens exactly when
            # `session.stop()` finalizes active tracks below. But `stop()`
            # also clears the live burst-payload cache
            # (`temporary_burst_payload`) as part of its own cleanup. So
            # burst bytes are harvested into this bounded, persistent cache
            # the moment each burst-role candidate is first observed -- while
            # the session is still fully live -- rather than looked up lazily
            # at assembly-tick time, which would otherwise race the exact
            # session.stop() call that makes the proposal assembleable in the
            # first place.
            burst_bytes_cache: dict[str, bytes] = {}
            # Same-Frame Species Evidence v1 (see docs/same-frame-species-
            # evidence-contract.md): mirrors `burst_bytes_cache` exactly,
            # for the same reason and on the same timing -- harvested from
            # the still-live session's own bounded temporary cache the
            # moment each `classifier_same_frame` candidate is first
            # observed, not lazily at assembly-tick time.
            same_frame_bytes_cache: dict[str, bytes] = {}

            def _harvest_immediately(result: ObservationResult) -> None:
                # Harvested Evidence Issuance / Missing-Evidence Closure v1:
                # `session.run()`'s own `on_result` calls this the instant
                # each frame's result is produced -- never deferred until
                # the whole up-to-`_BATCH_FRAMES`-frame batch below returns.
                # `LiveCameraNodeShadowSession._temporary_payloads`/`_same_
                # frame_temporary_payloads` are each their own small, fixed,
                # content-hash-keyed cache (capped at 8, independent of
                # `_MAX_CACHED_BURST_BYTES`/`_MAX_CACHED_SAME_FRAME_BYTES`
                # below) -- a busy batch in which more than 8 *separate*
                # frames each successfully capture a burst (several
                # concurrent generations, or several distinct subjects in
                # sequence, well within one real ~10-20-frame batch) used to
                # silently evict an early capture from that small cache
                # before the old, once-per-batch harvest loop further down
                # ever got to copy it into this much larger, properly-sized
                # cache -- a real proposal could then legitimately reach
                # `blocked_missing_evidence` with this larger cache nowhere
                # near full, because its own evidence was never lost from
                # *this* cache; it never survived long enough to arrive.
                # Harvesting per-frame, immediately, closes that gap
                # structurally rather than by enlarging any cache further.
                # See docs/candidate-visit-authority-contract.md "Evidence-
                # cache capacity" and `LiveCameraNodeShadowSession.run`'s own
                # `on_result` docstring.
                misses = _harvest_burst_bytes(session, result.evidence_candidates, burst_bytes_cache)
                misses += _harvest_same_frame_bytes(session, result.evidence_candidates, same_frame_bytes_cache)
                if misses:
                    with self._state_lock:
                        self._evidence_harvest_misses += misses

            try:
                # Right before this session starts actually pulling frames
                # from the Node -- the earliest point it can collide with an
                # already-running legacy live-view/monitoring camera session
                # for the same physical camera. Pausing here (rather than
                # any earlier, e.g. before the model even loads) means a
                # live view that's already healthy stays healthy for every
                # Start attempt that never reaches this point.
                self._pause_live_camera_session()
                session.start()
                with self._state_lock:
                    self._camera_connected = True
                    self._camera_message = "Connected to the Camera Node."
                    self._state = "observing"
                loop = asyncio.get_running_loop()
                last_tick = loop.time()
                # Observation Engine Session-Renewal Continuity v1: a single
                # `session.run()` interruption -- raised, or a batch that
                # completes with genuinely zero frames -- is no longer
                # automatically fatal to this whole session. Most of the
                # time this loop reconnects anyway (a fresh `/analysis-
                # stream` HTTP connection every ~10-second batch is already
                # the normal, healthy shape -- see docs/reconnect-continuity
                # -contract.md); `consecutive_transport_failures` only
                # tracks a run of *unsuccessful* attempts in a row, reset the
                # instant any attempt yields a real frame again. Nothing
                # about the accumulated `all_track_updates`/
                # `all_evidence_candidates`/the live `provider`'s own
                # tracker generation is touched while retrying, so a
                # recovered connection resumes the same encounter rather
                # than starting a new one -- see `AnalysisStreamRetryPolicy`.
                consecutive_transport_failures = 0
                while not self._stop_event.is_set():
                    try:
                        results = await session.run(maximum_frames=_BATCH_FRAMES, on_result=_harvest_immediately)
                    except (CameraNodeClientError, ValueError) as error:
                        code = _sanitized(error)
                        # Camera Node Connectivity & Recovery Diagnosis v1:
                        # surface the transport's own bounded failure-class
                        # detail (connect refused vs. timed out vs. reset vs.
                        # a bad HTTP response), when the raising site
                        # provided one, as auxiliary diagnostics only -- this
                        # never changes `code` (still the single value every
                        # retry/terminal check below matches against) and is
                        # simply overwritten by the next attempt, so it
                        # always reflects the most recent one.
                        failure_class = getattr(error, "failure_class", None)
                        if failure_class is not None:
                            with self._state_lock:
                                self._advanced["analysis_stream_failure_class"] = failure_class
                        if code in _TERMINAL_ANALYSIS_STREAM_ERROR_CODES:
                            with self._state_lock:
                                self._camera_connected = False
                                self._camera_message = f"Camera Node connection stopped: {code}."
                                self._stopped_reason = "camera_unavailable"
                            break
                        consecutive_transport_failures += 1
                        if not await self._await_transport_retry(
                            consecutive_failures=consecutive_transport_failures, reason=code,
                        ):
                            break
                        continue
                    if not results:
                        # A batch that completed cleanly (no exception) but
                        # delivered zero frames -- the honest shape of
                        # sustained `camera_busy` contention across an
                        # entire batch (see `AnalysisStreamRetryPolicy`'s own
                        # docstring), not proof the stream is permanently
                        # over: every batch is already its own fresh
                        # connection, so there is no persistent connection
                        # left to have "ended."
                        consecutive_transport_failures += 1
                        if not await self._await_transport_retry(
                            consecutive_failures=consecutive_transport_failures, reason="no_frames_received",
                        ):
                            break
                        continue
                    if consecutive_transport_failures:
                        # Recovered: restore honest healthy status the
                        # instant real frames arrive again -- "state returns
                        # to observing, freshness resumes, no stale terminal
                        # stopped_reason remains."
                        with self._state_lock:
                            self._camera_connected = True
                            self._camera_message = "Connected to the Camera Node."
                            self._advanced["analysis_stream_reconnect_recoveries"] = (
                                int(self._advanced.get("analysis_stream_reconnect_recoveries", 0)) + 1
                            )
                        consecutive_transport_failures = 0
                    # Today Coverage Truth v1: this batch just proved a real
                    # fresh frame, the same durable-exposure signal the
                    # legacy monitoring supervisor's own camera-health check
                    # already records -- checkpoint once per batch (already
                    # far coarser than per-frame; the durable model itself
                    # further throttles actual writes to a 45-second
                    # cadence), never during a recoverable retry/backoff
                    # window above, so a bounded reconnect never fragments or
                    # prematurely closes this session's coverage interval.
                    node_status = source.status()
                    self._checkpoint_observation_exposure(
                        repository,
                        healthy_at=self._clock(),
                        node_boot_id=node_status.node_boot_id,
                        node_service_version=node_status.node_service_version,
                    )
                    for result in results:
                        all_track_updates.extend(result.track_updates)
                        all_evidence_candidates.extend(result.evidence_candidates)
                        # Harmless, near-always-redundant fallback: `on_result`
                        # above already harvested this exact result the
                        # instant it was produced. Kept as defense in depth
                        # (idempotent -- `in cache: continue` -- and cheap)
                        # rather than removed, in case a future caller of
                        # `session.run()` ever omits `on_result`.
                        misses = _harvest_burst_bytes(session, result.evidence_candidates, burst_bytes_cache)
                        misses += _harvest_same_frame_bytes(
                            session, result.evidence_candidates, same_frame_bytes_cache,
                        )
                        if misses:
                            with self._state_lock:
                                self._evidence_harvest_misses += misses
                        # Rejected / Suppressed Detection Attribution v1: the
                        # one place this session previously discarded
                        # `result.detection_observations`/`detector_ran`
                        # entirely (see docs/rejected-detection-attribution
                        # -contract.md) -- every raw detector output and
                        # every finalized track generation, confirmed or
                        # not, now feeds the bounded counterfactual ledger.
                        self._counterfactual.observe_result(result)
                        for packet in result.frame_packets:
                            if packet.source_offset_ms is not None:
                                latest_known_offset_ms = max(latest_known_offset_ms, packet.source_offset_ms)
                            if self._acceptance_recorder is not None:
                                # Independent biological-encounter denominator
                                # (see docs/independent-encounter-denominator-
                                # design.md): a capability-safe tee of the
                                # exact already-decoded bytes this session
                                # itself just used for inference -- no new
                                # capture connection, no influence on any
                                # detection/tracking/admission decision below.
                                self._acceptance_recorder.maybe_record(packet)
                    with self._state_lock:
                        self._counts = ObservationEngineCounts(
                            track_updates_observed=len(all_track_updates),
                            evidence_candidates_observed=len(all_evidence_candidates),
                            proposals_observed=self._counts.proposals_observed,
                            candidates_created=self._counts.candidates_created,
                            candidates_suppressed=self._counts.candidates_suppressed,
                        )
                    now = loop.time()
                    if now - last_tick >= _ASSEMBLY_TICK_SECONDS:
                        last_tick = now
                        self._run_assembly_tick(
                            all_track_updates=all_track_updates,
                            all_evidence_candidates=all_evidence_candidates,
                            attempted_proposal_ids=attempted_proposal_ids,
                            burst_bytes_cache=burst_bytes_cache,
                            same_frame_bytes_cache=same_frame_bytes_cache,
                            adapter=adapter,
                            known_horizon_ms=latest_known_offset_ms,
                        )
            finally:
                final_results: tuple[ObservationResult, ...] = ()
                try:
                    final_results = session.stop()
                except Exception as teardown_error:  # noqa: BLE001 - see comment below
                    # Recovery-state-machine hardening (Camera Node
                    # Connectivity & Recovery Diagnosis v1, real 2026-08-20
                    # field incident): `except Exception`, matching `_run()`'s
                    # own generic handler below, deliberately never
                    # `BaseException` -- this branch does not re-raise, so it
                    # must never be able to swallow `CancelledError`/
                    # `SystemExit`/`KeyboardInterrupt`. A failure surfacing
                    # only here, during teardown -- most commonly `_verify_
                    # cuda_execution`'s own end-of-session CUDA self-check --
                    # must never skip the cleanup below (the finalize
                    # assembly tick and `provider.close()`). Before this fix, both were
                    # silently skipped whenever `session.stop()` raised: a
                    # fresh Start looked externally clean but the prior
                    # session's CUDA session/profiling directory was never
                    # released, and any still-pending episode was never
                    # finalized. This also must never overwrite an
                    # already-diagnosed camera-connectivity reason --
                    # `stopped_reason == "camera_unavailable"`, set only by
                    # the retry-exhaustion path above or the terminal-error-
                    # code branch, never by an ordinary user/session-end
                    # stop -- with a secondary teardown-time symptom that
                    # would hide the real, already-known root cause. Every
                    # other case (an ordinary clean stop, or a session that
                    # never hit a transport problem at all) keeps this
                    # module's exact pre-existing behavior: before this fix,
                    # `_run()`'s own generic `except Exception` handler set
                    # only `_state`/`_camera_message` from a propagating
                    # exception, never `_stopped_reason` -- deliberately
                    # matched here rather than widened, since `_stopped_
                    # reason` also drives `exposure_close_reason_for_
                    # transition` below. A genuine teardown-time failure --
                    # most seriously, real CUDA mixed-execution discovered
                    # only now -- still becomes the primary camera-facing
                    # reason, exactly as it always has, because it is the
                    # only diagnosis this session has.
                    with self._state_lock:
                        self._advanced["analysis_stream_teardown_error"] = _sanitized(teardown_error)
                        if self._stopped_reason != "camera_unavailable":
                            self._state = "error"
                            self._camera_message = _sanitized(teardown_error)
                for result in final_results:
                    all_track_updates.extend(result.track_updates)
                    all_evidence_candidates.extend(result.evidence_candidates)
                    misses = _harvest_burst_bytes(session, result.evidence_candidates, burst_bytes_cache)
                    misses += _harvest_same_frame_bytes(
                        session, result.evidence_candidates, same_frame_bytes_cache,
                    )
                    if misses:
                        with self._state_lock:
                            self._evidence_harvest_misses += misses
                    self._counterfactual.observe_result(result)
                    for packet in result.frame_packets:
                        if packet.source_offset_ms is not None:
                            latest_known_offset_ms = max(latest_known_offset_ms, packet.source_offset_ms)
                # The one tick that matters most for a short/naturally-ended
                # session: tracks `stop()` just finalized are now terminal,
                # and every burst byte any of them already captured survives
                # in `burst_bytes_cache` regardless of `stop()`'s own cache
                # clear above. `finalize=True`: the session itself is ending,
                # so no continuation could ever arrive -- every still-pending
                # episode is decided now rather than left waiting forever.
                self._run_assembly_tick(
                    all_track_updates=all_track_updates,
                    all_evidence_candidates=all_evidence_candidates,
                    attempted_proposal_ids=attempted_proposal_ids,
                    burst_bytes_cache=burst_bytes_cache,
                    same_frame_bytes_cache=same_frame_bytes_cache,
                    adapter=adapter,
                    known_horizon_ms=latest_known_offset_ms,
                    finalize=True,
                )
                with self._state_lock:
                    self._camera_connected = False
                provider.close()
        finally:
            # Hand the physical camera back the same unconditional way:
            # whenever this session's own loop ends, for *any* reason, not
            # only an explicit Stop. A no-op if `_pause_live_camera_session`
            # above was never reached, or if the user already explicitly
            # stopped the live session while it was paused (see
            # `LiveCameraSessionManager.resume_after_observation`).
            self._resume_live_camera_session()
            # Today Coverage Truth v1: close this session's own durable
            # monitoring-exposure interval the same unconditional way, for
            # the same reason -- whenever this loop ends, coverage truth
            # must stop growing with it, regardless of *why* it ended (see
            # `_close_observation_exposure`). A recoverable retry/backoff
            # window above never reaches this `finally` at all -- the loop
            # is still running -- so a bounded reconnect can never trigger
            # this close.
            self._close_observation_exposure(repository)
            # Authority reverts to shadow whenever this session's own loop
            # ends, for *any* reason -- natural stream end, a transport
            # error, or an explicit Stop -- not only when a caller happens
            # to call `.stop()` directly. A session that has already died
            # must never leave candidate authority silently active with
            # nothing watching it. `stop()`'s own revert (see below) is an
            # additional safeguard for a thread that fails to join in time,
            # not the only place this happens.
            try:
                repository.set_observation_authority_mode(
                    ObservationAuthorityMode.shadow, stream_id=self.stream_id,
                )
            except Exception:  # pragma: no cover - defensive: cleanup must never raise
                pass
            repository.close()

    async def _await_transport_retry(self, *, consecutive_failures: int, reason: str) -> bool:
        """Bounded, Stop-responsive wait between two `session.run()`
        attempts for one recoverable Camera Node analysis-stream
        interruption (see `AnalysisStreamRetryPolicy`). Returns `True` if
        the caller should try `session.run()` again; `False` once the
        bounded retry budget is exhausted or the user explicitly stopped
        mid-wait -- both of which the caller treats exactly like the
        unconditional break this replaces.

        Honest status throughout (product requirement: during a bounded
        reconnect, UI/API state must not falsely report that everything is
        healthy): `camera_connected` goes false and `camera_message` names
        the attempt the moment the first recoverable interruption is seen.
        `_state`/`observing` are deliberately never touched here --
        Observation stays logically active the whole time, exactly as
        docs/observation-session-renewal-continuity-contract.md requires;
        only the camera-health fields (already this module's existing,
        established honesty channel -- see the "Camera health/status
        correction" contract) reflect the degraded window.
        """

        policy = self._retry_policy
        exhausted = consecutive_failures >= policy.maximum_consecutive_failures
        with self._state_lock:
            self._camera_connected = False
            if exhausted:
                self._camera_message = f"Camera Node connection stopped: {reason}."
                self._stopped_reason = "camera_unavailable"
            else:
                self._camera_message = (
                    f"Reconnecting to the Camera Node… (attempt {consecutive_failures} of "
                    f"{policy.maximum_consecutive_failures}; last signal: {reason})"
                )
            self._advanced["analysis_stream_consecutive_failures"] = consecutive_failures
        if exhausted:
            return False
        # `Event.wait` returns True the moment the event is set (even if
        # that happens well before the timeout), so an explicit Stop
        # requested mid-backoff is noticed immediately rather than only
        # after the full backoff elapses -- mirroring the exact
        # `asyncio.to_thread(available.wait, ...)` pattern `session.run()`
        # itself already uses for the same reason.
        stopped = await asyncio.to_thread(self._stop_event.wait, policy.backoff_seconds)
        return not stopped

    def _pause_live_camera_session(self) -> None:
        """Best-effort: a bug here must never prevent Observation Engine
        from starting -- exactly how `report_metadata` above is already
        allowed to fail without breaking Start."""

        if self._live_camera_sessions is None:
            return
        try:
            self._live_camera_sessions.pause_for_observation(self.stream_id)
        except Exception:  # pragma: no cover - defensive: must never break Start
            pass

    def _resume_live_camera_session(self) -> None:
        """Best-effort, matching `_pause_live_camera_session` -- a bug here
        must never prevent Stop from completing or authority from
        reverting."""

        if self._live_camera_sessions is None:
            return
        try:
            self._live_camera_sessions.resume_after_observation(self._playback_config)
        except Exception:  # pragma: no cover - defensive: must never break Stop
            pass

    def _checkpoint_observation_exposure(
        self,
        repository: ProductRepository,
        *,
        healthy_at: datetime,
        node_boot_id: str | None = None,
        node_service_version: str | None = None,
    ) -> None:
        """Today Coverage Truth v1 (see docs/todays-coverage-truth-contract
        .md): record one durable monitoring-exposure checkpoint for a batch
        that just delivered at least one real frame -- never a raw transport
        retry/backoff window (see `_await_transport_retry`, which never
        calls this). Best-effort, matching every other per-batch bookkeeping
        call in this loop: exposure accounting must never be able to break
        live analysis.

        Boot Identity + Autonomous Recovery v1: also reuses this exact
        already-throttled checkpoint (never a new write cadence -- see
        "Performance" in docs/camera-node-installer-design.md) to persist
        the Node's last-seen boot identity, independent of whether a
        session happens to be running later -- see
        `ProductRepository.record_observation_exposure_frame`. A detected
        boot transition (same node, fresh reboot mid-session) is surfaced
        into `advanced` so the host can tell that apart from an ordinary
        benign reconnect (same boot_id) -- see "same node + new boot" in
        the milestone's deterministic test list.
        """

        self._last_healthy_frame_at = healthy_at
        try:
            outcome = repository.record_observation_exposure_frame(
                stream_id=self.stream_id,
                runtime_generation_id=self._runtime_generation_id,
                healthy_at=healthy_at,
                now=healthy_at,
                node_boot_id=node_boot_id,
                node_service_version=node_service_version,
            )
        except Exception:  # pragma: no cover - defensive: must never break analysis
            return
        if outcome is not None and outcome.boot_transition_detected:
            with self._state_lock:
                self._advanced["camera_node_boot_transitions_this_session"] = (
                    int(self._advanced.get("camera_node_boot_transitions_this_session", 0)) + 1
                )
                self._advanced["camera_node_fresh_boot_detected"] = True

    def _close_observation_exposure(self, repository: ProductRepository) -> None:
        """Close this session's own open durable monitoring-exposure
        interval, if any, whenever `_run_async`'s main loop ends for *any*
        reason -- mirroring `_resume_live_camera_session`/the authority-
        revert call right below this one's own call site, both of which are
        already unconditional cleanup for the identical reason. Closes at
        the best known real fresh-frame evidence
        (`_last_healthy_frame_at`), never at an assumed outage boundary; a
        safe no-op if no interval was ever opened (for example a session
        that failed before its first real frame ever arrived). `reason` is
        mapped through the same shared vocabulary the legacy durable-
        monitoring-supervisor path already uses, so both writers record one
        consistent, honest close reason."""

        close_reason = exposure_close_reason_for_transition(self._stopped_reason or "camera_unavailable")
        try:
            repository.close_observation_exposure(
                stream_id=self.stream_id,
                close_reason=close_reason,
                now=self._clock(),
                last_healthy_at=self._last_healthy_frame_at,
            )
        except Exception:  # pragma: no cover - defensive: cleanup must never raise
            pass

    def _schedule_automatic_identification(self, visit_id: str) -> None:
        """Best-effort hand-off to the bounded, single-worker automatic
        BioCLIP assist for one freshly-created candidate Visit. Matches
        `_pause_live_camera_session`'s own defensive convention: a bug here,
        an unavailable local model, or a repository failure must never
        break this Stream's own tick loop or Visit admission. Uses a fresh
        repository handle (not the one this session already holds open for
        its own tick loop) so the assist's own background thread never
        shares a repository call in flight with this thread -- the same
        separation the existing legacy-motion automatic-identification call
        site (`api.main._maybe_schedule_automatic_review_identification`)
        already relies on."""

        if self._automatic_identification_assist is None:
            return
        try:
            repository = self._repository_factory()
        except Exception:  # pragma: no cover - defensive: must never break admission
            return
        try:
            self._automatic_identification_assist.schedule(
                repository,
                visit_id=visit_id,
                on_update=self._record_automatic_identification_update,
            )
        except Exception:  # pragma: no cover - defensive: must never break admission
            pass

    def _record_automatic_identification_update(self, update: object) -> None:
        """Bounded, best-effort diagnostics only -- the latest automatic
        identification status, alongside the other free-form `_advanced`
        facts this session already exposes. Never grows unboundedly over a
        long session, and a formatting bug here must never surface as a
        tick-loop failure."""

        try:
            as_dict = update.as_dict()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover - defensive: diagnostics must never raise
            return
        with self._state_lock:
            self._advanced["automatic_identification"] = as_dict

    def _run_assembly_tick(
        self,
        *,
        all_track_updates: list[TrackUpdate],
        all_evidence_candidates: list[EvidenceCandidate],
        attempted_proposal_ids: set[str],
        burst_bytes_cache: dict[str, bytes],
        same_frame_bytes_cache: dict[str, bytes] | None = None,
        adapter: CandidateVisitAuthorityAdapter,
        known_horizon_ms: int | None = None,
        finalize: bool = False,
    ) -> None:
        """Reruns the unmodified, bounded, post-hoc Stage 6.19 assembler over
        every track update observed so far -- exactly
        `candidate_visit_authority_cli.py`'s own periodic-tick convention,
        never a new live incremental assembler.

        `known_horizon_ms`/`finalize` implement the Visit Continuity /
        Provisional Admission Fix v1 (see docs/tracklet-visit-assembly
        -contract.md "Episode finality"): `finalize=True` (the session
        -ending tick) omits the horizon entirely, so every proposal is
        evaluated as already final -- correct, because the stream itself has
        ended and no continuation could ever arrive. Otherwise
        `known_horizon_ms` is passed straight through to `assemble_visit_
        episodes`, which alone decides -- from facts it already owns --
        whether each proposal's own tail boundary might still change.

        Ambiguous boundary arbitration (Admission Recall Investigation +
        Conditional Fix v1, see "Ambiguous boundary arbitration" in
        docs/tracklet-visit-assembly-contract.md): every tick's full,
        freshly-assembled `proposals` -- not just the ones not yet
        attempted -- is first passed to `resolve_ambiguous_boundary_
        arbitration`, exactly once, so this tick sees a consistent
        snapshot. A proposal in its `deferred_ids` is excluded from `new_
        proposals` below and simply never attempted this tick (identical in
        spirit to how an ordinary `continuation_pending` proposal is
        already left out of `attempted_proposal_ids` so it is naturally
        re-offered later); a proposal in `resolved_winner_ids` is attempted
        with `ambiguous_boundary_resolved=True`, letting it bypass a
        permanent `blocked_ambiguous_boundary` verdict its own cluster has
        already resolved in its favor. Every other proposal (empty
        `ambiguous_adjacent_proposal_ids`, or a non-winning, now-stable
        cluster member) is attempted exactly as before this fix.
        """

        evidence_by_generation: dict[str, list[str]] = {}
        for candidate in all_evidence_candidates:
            if candidate.track_generation_id:
                evidence_by_generation.setdefault(candidate.track_generation_id, []).append(
                    candidate.media_asset_id
                )
        tracklets = build_tracklets(
            tuple(all_track_updates), stream_id=self.stream_id,
            evidence_candidate_ids_by_generation={key: tuple(value) for key, value in evidence_by_generation.items()},
        )
        proposals = assemble_visit_episodes(
            tracklets, known_horizon_ms=None if finalize else known_horizon_ms,
        ).proposals
        arbitration = resolve_ambiguous_boundary_arbitration(proposals)
        new_proposals = [
            item for item in proposals
            if item.proposal_id not in attempted_proposal_ids and item.proposal_id not in arbitration.deferred_ids
        ]
        if not new_proposals:
            return

        candidates_by_id = {item.media_asset_id: item for item in all_evidence_candidates}
        same_frame_cache = same_frame_bytes_cache or {}
        for proposal in new_proposals:
            relevant = tuple(
                candidates_by_id[media_id]
                for media_id in proposal.evidence_candidate_ids
                if media_id in candidates_by_id
            )
            # Same-Frame Species Evidence v1: `same_frame_cache` is keyed by
            # its own distinct `"shadow-same-frame:..."` media_asset_id
            # namespace (see `camera_node_live.py`), so this union can never
            # collide with a burst payload -- both are simply looked up by
            # whatever id `relevant` actually names.
            evidence_bytes = {
                candidate.media_asset_id: burst_bytes_cache[candidate.media_asset_id]
                for candidate in relevant
                if candidate.media_asset_id in burst_bytes_cache
            } | {
                candidate.media_asset_id: same_frame_cache[candidate.media_asset_id]
                for candidate in relevant
                if candidate.media_asset_id in same_frame_cache
            }
            decided_at = datetime.now(UTC)
            outcome = adapter.attempt_candidate(
                proposal, evidence_candidates=relevant, evidence_bytes=evidence_bytes,
                observed_at=decided_at,
                ambiguous_boundary_resolved=proposal.proposal_id in arbitration.resolved_winner_ids,
            )
            # Rejected / Suppressed Detection Attribution v1: recorded
            # regardless of outcome (including a genuine "created"), so
            # both "why was this Visit created" and "why was this potential
            # Visit not created" are answerable from the same bounded
            # ledger -- replacing the bare `self._suppressed[outcome] += 1`
            # count below (kept, unmodified, for the existing basic
            # diagnostics surface) with full, reconstructable lineage. This
            # is the exact proposal/geometry/confidence detail a retried
            # `blocked_continuation_pending` re-evaluation on a later tick
            # previously discarded completely on every attempt but the
            # last.
            self._counterfactual.record_proposal_outcome(
                proposal, outcome=outcome.outcome, reason=outcome.reason, visit_id=outcome.visit_id,
                decided_at=decided_at, known_horizon_ms=known_horizon_ms,
            )
            # A proposal blocked only because its own episode boundary is
            # not yet final (`blocked_continuation_pending`) is never marked
            # permanently attempted: the identical proposal id must be
            # re-offered on a later tick, either because a continuation
            # tracklet has since merged into it (a different, larger
            # proposal id, which is "new" anyway) or because enough of the
            # stream has now been observed for its own boundary to finalize.
            # Every other outcome -- created, idempotent, or any other
            # block -- is a resolved fact about this exact proposal id and
            # must never be revisited (see `RETRYABLE_OUTCOMES`).
            if outcome.outcome not in RETRYABLE_OUTCOMES:
                attempted_proposal_ids.add(proposal.proposal_id)
            with self._state_lock:
                self._counts = ObservationEngineCounts(
                    track_updates_observed=self._counts.track_updates_observed,
                    evidence_candidates_observed=self._counts.evidence_candidates_observed,
                    proposals_observed=self._counts.proposals_observed + 1,
                    candidates_created=self._counts.candidates_created + (1 if outcome.created else 0),
                    candidates_suppressed=self._counts.candidates_suppressed
                    + (0 if outcome.created else 1),
                )
                if outcome.created:
                    self._last_candidate_visit_id = outcome.visit_id
                elif outcome.outcome in BLOCKED_OUTCOMES or outcome.outcome in REJECTED_OUTCOMES or outcome.outcome in {
                    "blocked_privacy_zone", "blocked_missing_evidence", "blocked_scene_confusor_suspected", "failed",
                }:
                    self._suppressed[outcome.outcome] = self._suppressed.get(outcome.outcome, 0) + 1
                if outcome.outcome == "blocked_session_limit" and not self._candidate_authority_exhausted:
                    # Legitimate, in-session budget exhaustion (see "Health/
                    # diagnostic truth for budget exhaustion" in
                    # docs/candidate-visit-authority-contract.md) -- truthful
                    # and sticky for the rest of this running session,
                    # matching `blocked_session_limit`'s own permanent-for-
                    # this-activation-window semantics. Never raw internal
                    # counters here (those stay in `advanced`); a plain-
                    # language fact plus the one safe, always-correct action.
                    self._candidate_authority_exhausted = True
                    self._candidate_authority_message = (
                        "This session has reached its automatic Visit-creation limit for now. "
                        "Existing Visits are unaffected. Stop and start observation again to "
                        "resume creating new Visits."
                    )
            # Automatic Species Suggestion v1: a durably-created candidate
            # Visit (evidence already committed by `create_candidate_visit_
            # from_proposal` before `attempt_candidate` returned above) is
            # offered to the existing bounded, single-worker BioCLIP assist
            # -- never run inline here. Species inference must not add any
            # latency to this tick loop, which is also this Stream's only
            # path for observing new frames; a slow or unavailable local
            # model can only ever leave a Visit at its honest Animal/Unknown
            # default; it can never block or fail candidate admission.
            if outcome.created and outcome.visit_id:
                self._schedule_automatic_identification(outcome.visit_id)


# Visit Authority Budget + Ambiguous-Boundary Recall Closure v1: raised from
# the original 8 to 32. Real, evidenced 2026-08-19 field defect: reconstructing
# both missed strong encounters against the real captured counterfactual
# ledger found the proposal that actually escaped `blocked_ambiguous_
# boundary` (either never ambiguous, or an arbitration winner) still
# permanently failed at evidence admission (`reject_no_identification_or_
# context`/`blocked_missing_evidence`) in both clusters -- not because no
# evidence was ever captured, but because this session-global cache,
# evicted purely by insertion count with no awareness of which pending
# proposal still needs which bytes, had already cycled past it. A proposal
# legitimately delayed by ambiguous-boundary/continuation-pending
# resolution (which can span the full `VisitAssemblyConfiguration.
# ambiguous_gap_ms`, 45s, or longer for a still-growing cluster) can easily
# have its own already-captured evidence evicted by unrelated activity
# elsewhere in a busy real stream before its own delayed admission attempt
# ever runs. 32 was a deliberately generous multiple of the old bound (real
# cluster generation counts measured 34 and 40 within a single encounter),
# while remaining a small, bounded in-memory footprint.
#
# End-to-End Bird Encounter Recall Closure v1: raised again, from 32 to 128.
# A real, evidenced 2026-08-19 field defect -- a *different*, busier real
# session (21 candidates/227 proposals/1336 evidence candidates in 92
# minutes, versus the ~98-minute session that motivated the 32 bound) still
# exhausted it: a genuine 149.6s, 6-generation, 0.816-max-confidence
# encounter (six generations at stable feeder-perch geometry -- one real,
# mostly-stationary bird, not six subjects) was legitimately deferred
# `blocked_continuation_pending` for a real 183.5 seconds before permanently
# failing `reject_no_identification_or_context`; a second, independent real
# case in the same session (30.3s, single-generation, 0.815 max confidence,
# 12 strong detections) failed `blocked_missing_evidence` after an even
# shorter ~34s delay. This session's own measured evidence-candidate rate
# (1336 over 5512s, ~0.242/s) projected across a realistic 150-280s
# continuation-pending delay window is ~36-68 candidates -- past the 32
# bound. 128 is the same relative (4x) jump the original 8->32 fix itself
# used, verified directly against this exact real failure shape:
# `test_delayed_proposal_survives_a_busier_real_session_shape_than_the_32_
# bound_covers` in tests/test_engine_runtime.py fails at 32 (RED) and
# passes at 128 (GREEN). Still a capacity fix, not an evidence-quality
# threshold change -- every requirement `candidate_quality_gate.
# evaluate_evidence_admission` enforces is unchanged. This remains a bound,
# not a structural fix: an arbitrarily busier or longer-delayed session
# could still in principle exhaust it, since eviction is still purely
# insertion-count-based with no awareness of which pending proposal still
# needs which bytes -- a pending-proposal-aware eviction policy would close
# that gap structurally, but is a materially larger change than this
# capacity bump and is left as a disclosed follow-up, not undertaken here.
_MAX_CACHED_BURST_BYTES = 128
_MAX_CACHED_SAME_FRAME_BYTES = 128


def _harvest_burst_bytes(
    session: LiveCameraNodeShadowSession,
    candidates: tuple[EvidenceCandidate, ...],
    cache: dict[str, bytes],
) -> int:
    """Copy any new burst-role candidate's bytes out of the session's own
    temporary payload cache immediately, while the session is still live --
    see the "burst_bytes_cache" note in `_run_async` for why this cannot be
    deferred to assembly-tick time, and `LiveCameraNodeShadowSession.run`'s
    `on_result` docstring for why it also cannot wait for a whole batch.
    Bounded the same way the session's own `temporary_burst_payload` cache
    already is.

    Returns the count of candidates in this call whose content hash was not
    found in the session's own cache. This is always a genuine "captured,
    then lost before harvest" fact, never "never captured": a
    `high_resolution_burst`-role `EvidenceCandidate` only ever exists after
    `LiveCameraNodeShadowSession._process_frame` has already inserted its
    payload into that same cache at least once. See `_EngineSession.
    _evidence_harvest_misses` for where callers accumulate and surface
    this."""

    misses = 0
    for candidate in candidates:
        if candidate.role != "high_resolution_burst" or candidate.media_asset_id in cache:
            continue
        content_hash = dict(candidate.quality_facts).get("content_hash")
        if not isinstance(content_hash, str):
            continue
        payload = session.temporary_burst_payload(content_hash)
        if not payload:
            misses += 1
            continue
        cache[candidate.media_asset_id] = payload
        while len(cache) > _MAX_CACHED_BURST_BYTES:
            cache.pop(next(iter(cache)))
    return misses


def _harvest_same_frame_bytes(
    session: LiveCameraNodeShadowSession,
    candidates: tuple[EvidenceCandidate, ...],
    cache: dict[str, bytes],
) -> int:
    """Same-Frame Species Evidence v1: mirrors `_harvest_burst_bytes` exactly
    for the `classifier_same_frame` role and `session.
    temporary_same_frame_payload`'s own independently-bounded cache,
    including its return-value meaning."""

    misses = 0
    for candidate in candidates:
        if candidate.role != CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE or candidate.media_asset_id in cache:
            continue
        content_hash = dict(candidate.quality_facts).get("content_hash")
        if not isinstance(content_hash, str):
            continue
        payload = session.temporary_same_frame_payload(content_hash)
        if not payload:
            misses += 1
            continue
        cache[candidate.media_asset_id] = payload
        while len(cache) > _MAX_CACHED_SAME_FRAME_BYTES:
            cache.pop(next(iter(cache)))
    return misses


class ObservationEngineSessionManager:
    """App-owned singleton: at most one running background session per
    Stream, mirroring `LiveCameraSessionManager`'s own established
    convention exactly."""

    def __init__(
        self,
        *,
        repository_factory: Callable[[], ProductRepository],
        provider_loader: ProviderLoader = _load_real_provider,
        transport_factory: TransportFactory = _default_transport_factory,
        capture_profile_alignment_factory: CaptureProfileAlignmentFactory = _default_capture_profile_alignment,
        live_camera_sessions: LiveCameraSessionCoordinator | None = None,
        automatic_identification_assist: AutomaticReviewIdentificationAssist | None = None,
        analysis_stream_retry_policy: AnalysisStreamRetryPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        acceptance_recording_root: Path | None = None,
        acceptance_recorder_config_factory: AcceptanceRecorderConfigFactory | None = None,
    ) -> None:
        self._repository_factory = repository_factory
        self._provider_loader = provider_loader
        self._transport_factory = transport_factory
        self._capture_profile_alignment_factory = capture_profile_alignment_factory
        self._live_camera_sessions = live_camera_sessions
        self._automatic_identification_assist = automatic_identification_assist
        self._analysis_stream_retry_policy = analysis_stream_retry_policy or AnalysisStreamRetryPolicy()
        # Today Coverage Truth v1: test-only override, forwarded to every
        # `_EngineSession` this manager constructs -- see `_EngineSession
        # .__init__`'s own `clock` docstring.
        self._clock = clock
        # Independent biological-encounter denominator (Visit Authority
        # Budget + Ambiguous-Boundary Recall Closure v1): `None` unless the
        # process was explicitly configured with `MOCKINGBIRD_ACCEPTANCE_
        # RECORDING_DIR` (see `main.get_observation_engine_session_manager`)
        # -- off by default for every normal product Start. When set, every
        # new `_EngineSession` this manager creates gets its own bounded
        # recorder writing to a fresh, stream- and start-time-scoped
        # subdirectory, so concurrent/repeated Streams/sessions never
        # collide or overwrite each other's manifest.
        # End-to-End Bird Encounter Recall Closure v1: `None` reproduces the
        # exact prior behavior (`AcceptanceRecorderConfig(output_dir=...)`,
        # every field defaulted) -- only an explicit caller-supplied factory
        # (in practice `main.py` wiring `acceptance_recorder_config_from_
        # env`) can widen/tighten one session's cadence or bounds.
        self._acceptance_recorder_config_factory: AcceptanceRecorderConfigFactory = (
            acceptance_recorder_config_factory or (lambda output_dir: AcceptanceRecorderConfig(output_dir=output_dir))
        )
        self._acceptance_recording_root = acceptance_recording_root
        self._lock = threading.RLock()
        self._sessions: dict[str, _EngineSession] = {}

    def start(
        self,
        stream_id: str,
        playback_config: StreamLivePlaybackConfig,
        *,
        privacy_ignore_regions: tuple[tuple[float, float, float, float], ...] = (),
        provider_config_path: Path | None = None,
    ) -> ObservationEngineSessionStatus:
        with self._lock:
            existing = self._sessions.get(stream_id)
            if existing is not None and existing.is_active:
                return existing.snapshot()
            if existing is not None:
                existing.stop()
            acceptance_recorder = None
            if self._acceptance_recording_root is not None:
                started_at = (self._clock or (lambda: datetime.now(UTC)))()
                session_dir = self._acceptance_recording_root / stream_id / started_at.strftime("%Y%m%dT%H%M%SZ")
                acceptance_recorder = BoundedFrameSampleRecorder(
                    self._acceptance_recorder_config_factory(session_dir)
                )
            session = _EngineSession(
                stream_id=stream_id,
                playback_config=playback_config,
                provider_config_path=resolve_provider_config_path(provider_config_path),
                acceptance_recorder=acceptance_recorder,
                privacy_ignore_regions=privacy_ignore_regions,
                repository_factory=self._repository_factory,
                provider_loader=self._provider_loader,
                transport_factory=self._transport_factory,
                capture_profile_alignment_factory=self._capture_profile_alignment_factory,
                live_camera_sessions=self._live_camera_sessions,
                automatic_identification_assist=self._automatic_identification_assist,
                analysis_stream_retry_policy=self._analysis_stream_retry_policy,
                clock=self._clock,
            )
            self._sessions[stream_id] = session
            session.start()
            return session.snapshot()

    def stop(self, stream_id: str) -> ObservationEngineSessionStatus | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        session.stop()
        return session.snapshot()

    def status(self, stream_id: str) -> ObservationEngineSessionStatus | None:
        with self._lock:
            session = self._sessions.get(stream_id)
        return session.snapshot() if session is not None else None

    def counterfactual_query(
        self, stream_id: str, *, start_offset_ms: int, end_offset_ms: int, roi: BoundingBox | None = None,
    ) -> CounterfactualWindowResult | None:
        """`None` only when this Stream has never started an Observation
        Engine session in this process at all (mirroring `status()`'s own
        "no session object exists yet" convention) -- never for a session
        that simply has no matching lineage, which instead returns an
        honest, empty `CounterfactualWindowResult`."""

        with self._lock:
            session = self._sessions.get(stream_id)
        if session is None:
            return None
        return session.counterfactual_query(start_offset_ms=start_offset_ms, end_offset_ms=end_offset_ms, roi=roi)

    def stop_all(self, *, reason: str = "app_shutdown") -> None:
        with self._lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            session.stop(reason=reason)
