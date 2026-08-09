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
"""

from __future__ import annotations

import asyncio
import os
import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable, Protocol

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
    ObservationAuthorityMode,
)
from mockingbird.observation.contracts import EvidenceCandidate, TrackUpdate
from mockingbird.observation.frame_driven_provider import (
    FrameDrivenObservationProvider,
    FrameDrivenProviderConfiguration,
)
from mockingbird.observation.onnx_provider import OnnxCudaObservationProvider, OnnxModelBundle
from mockingbird.observation.visit_episode_assembler import assemble_visit_episodes, build_tracklets
from mockingbird.repository.product_repository import ProductRepository, StreamLivePlaybackConfig
from mockingbird.source_providers.camera_node import CameraNodeClientError

PROVIDER_CONFIG_PATH_ENV = "MOCKINGBIRD_OBSERVATION_PROVIDER_CONFIG_PATH"
DEFAULT_PROVIDER_CONFIG_PATH = Path("data/models/observation-frame-driven/provider-config.json")

_BATCH_FRAMES = 20
_ASSEMBLY_TICK_SECONDS = 10.0
_STOP_JOIN_TIMEOUT_SECONDS = 20.0
_MAX_SUPPRESSED_REASONS = 8

ObservationEngineState = str  # "stopped" | "starting" | "observing" | "stopping" | "error"


class _DetectorProvenance(Protocol):
    provider_id: str


ProviderLoader = Callable[[Path], tuple[FrameDrivenObservationProvider, _DetectorProvenance]]
TransportFactory = Callable[[StreamLivePlaybackConfig, str], CameraNodeLiveTransport]


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


def resolve_provider_config_path(override: Path | None = None) -> Path:
    """Where the accepted Observation Engine's model-bundle configuration
    lives -- an explicit local file the user (or a future setup flow)
    already supplied, exactly like the existing `replay-benchmark`/
    `candidate-authority-trial` CLI convention documented in README.md. The
    app never downloads or generates this file."""

    if override is not None:
        return override
    configured = os.environ.get(PROVIDER_CONFIG_PATH_ENV)
    return Path(configured) if configured else DEFAULT_PROVIDER_CONFIG_PATH


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
    counts: ObservationEngineCounts = field(default_factory=ObservationEngineCounts)
    advanced: dict[str, object] = field(default_factory=dict)


def _sanitized(error: BaseException) -> str:
    """Never let a raw exception message (which can carry a local path or
    transport detail) reach product status; every error this module raises
    itself is already a short stable code, so this is a bounded fallback for
    a genuinely unexpected third-party exception."""

    text = str(error) or error.__class__.__name__
    return text[:200]


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
    ) -> None:
        self.stream_id = stream_id
        self._playback_config = playback_config
        self._provider_config_path = provider_config_path
        self._privacy_ignore_regions = privacy_ignore_regions
        self._repository_factory = repository_factory
        self._provider_loader = provider_loader
        self._transport_factory = transport_factory
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._state_lock = threading.RLock()
        self._state: ObservationEngineState = "starting"
        self._started_at: datetime | None = None
        self._stopped_at: datetime | None = None
        self._stopped_reason: str | None = None
        self._camera_connected = False
        self._camera_message = "Not yet connected to the Camera Node."
        self._engine_available = False
        self._engine_message = "Observation Engine has not started yet."
        self._counts = ObservationEngineCounts()
        self._suppressed: dict[str, int] = {}
        self._last_candidate_visit_id: str | None = None
        self._advanced: dict[str, object] = {}

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
                repository.set_observation_authority_mode(ObservationAuthorityMode.shadow)
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
                "error": self._engine_message if not self._camera_connected else self._camera_message,
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
                counts=counts,
                advanced=dict(self._advanced),
            )

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

        try:
            provider, detector = self._provider_loader(self._provider_config_path)
        except (ValueError, OSError, RuntimeError) as error:
            with self._state_lock:
                self._state = "error"
                self._engine_available = False
                self._engine_message = (
                    "The Observation Engine could not start. Confirm a local model bundle is "
                    f"configured (see {PROVIDER_CONFIG_PATH_ENV}) and a compatible GPU is "
                    f"available. ({_sanitized(error)})"
                )
            return

        with self._state_lock:
            self._engine_available = True
            self._engine_message = "Observation Engine is running."
            self._advanced["provider_key"] = provider.provider_id
            self._advanced["detector_provider_key"] = getattr(detector, "provider_id", "onnx-cuda")

        repository = self._repository_factory()
        try:
            activation = repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit)
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
            session = LiveCameraNodeShadowSession(
                source=source, transport=transport, provider=provider,
                evidence_profile_id=config.camera_node_evidence_profile_id,
            )
            adapter = CandidateVisitAuthorityAdapter(
                repository, detector_provenance=detector.provider_id, tracker_provenance=provider.provider_id,
                provider_key=provider.provider_id,
            )

            all_track_updates: list[TrackUpdate] = []
            all_evidence_candidates: list[EvidenceCandidate] = []
            attempted_proposal_ids: set[str] = set()
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

            try:
                session.start()
                with self._state_lock:
                    self._camera_connected = True
                    self._camera_message = "Connected to the Camera Node."
                    self._state = "observing"
                loop = asyncio.get_running_loop()
                last_tick = loop.time()
                while not self._stop_event.is_set():
                    try:
                        results = await session.run(maximum_frames=_BATCH_FRAMES)
                    except (CameraNodeClientError, ValueError) as error:
                        with self._state_lock:
                            self._camera_connected = False
                            self._camera_message = f"Camera Node connection stopped: {_sanitized(error)}."
                            self._stopped_reason = "camera_unavailable"
                        break
                    if not results:
                        with self._state_lock:
                            self._stopped_reason = "stream_ended"
                        break
                    for result in results:
                        all_track_updates.extend(result.track_updates)
                        all_evidence_candidates.extend(result.evidence_candidates)
                        _harvest_burst_bytes(session, result.evidence_candidates, burst_bytes_cache)
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
                            adapter=adapter,
                        )
            finally:
                final_results = session.stop()
                for result in final_results:
                    all_track_updates.extend(result.track_updates)
                    all_evidence_candidates.extend(result.evidence_candidates)
                    _harvest_burst_bytes(session, result.evidence_candidates, burst_bytes_cache)
                # The one tick that matters most for a short/naturally-ended
                # session: tracks `stop()` just finalized are now terminal,
                # and every burst byte any of them already captured survives
                # in `burst_bytes_cache` regardless of `stop()`'s own cache
                # clear above.
                self._run_assembly_tick(
                    all_track_updates=all_track_updates,
                    all_evidence_candidates=all_evidence_candidates,
                    attempted_proposal_ids=attempted_proposal_ids,
                    burst_bytes_cache=burst_bytes_cache,
                    adapter=adapter,
                )
                with self._state_lock:
                    self._camera_connected = False
                provider.close()
        finally:
            # Authority reverts to shadow whenever this session's own loop
            # ends, for *any* reason -- natural stream end, a transport
            # error, or an explicit Stop -- not only when a caller happens
            # to call `.stop()` directly. A session that has already died
            # must never leave candidate authority silently active with
            # nothing watching it. `stop()`'s own revert (see below) is an
            # additional safeguard for a thread that fails to join in time,
            # not the only place this happens.
            try:
                repository.set_observation_authority_mode(ObservationAuthorityMode.shadow)
            except Exception:  # pragma: no cover - defensive: cleanup must never raise
                pass
            repository.close()

    def _run_assembly_tick(
        self,
        *,
        all_track_updates: list[TrackUpdate],
        all_evidence_candidates: list[EvidenceCandidate],
        attempted_proposal_ids: set[str],
        burst_bytes_cache: dict[str, bytes],
        adapter: CandidateVisitAuthorityAdapter,
    ) -> None:
        """Reruns the unmodified, bounded, post-hoc Stage 6.19 assembler over
        every track update observed so far -- exactly
        `candidate_visit_authority_cli.py`'s own periodic-tick convention,
        never a new live incremental assembler."""

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
        proposals = assemble_visit_episodes(tracklets).proposals
        new_proposals = [item for item in proposals if item.proposal_id not in attempted_proposal_ids]
        if not new_proposals:
            return

        candidates_by_id = {item.media_asset_id: item for item in all_evidence_candidates}
        for proposal in new_proposals:
            attempted_proposal_ids.add(proposal.proposal_id)
            relevant = tuple(
                candidates_by_id[media_id]
                for media_id in proposal.evidence_candidate_ids
                if media_id in candidates_by_id
            )
            evidence_bytes = {
                candidate.media_asset_id: burst_bytes_cache[candidate.media_asset_id]
                for candidate in relevant
                if candidate.media_asset_id in burst_bytes_cache
            }
            outcome = adapter.attempt_candidate(
                proposal, evidence_candidates=relevant, evidence_bytes=evidence_bytes,
                observed_at=datetime.now(UTC),
            )
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
                elif outcome.outcome in BLOCKED_OUTCOMES or outcome.outcome in REJECTED_OUTCOMES or outcome.outcome in {"blocked_privacy_zone", "blocked_missing_evidence", "failed"}:
                    self._suppressed[outcome.outcome] = self._suppressed.get(outcome.outcome, 0) + 1


_MAX_CACHED_BURST_BYTES = 8


def _harvest_burst_bytes(
    session: LiveCameraNodeShadowSession,
    candidates: tuple[EvidenceCandidate, ...],
    cache: dict[str, bytes],
) -> None:
    """Copy any new burst-role candidate's bytes out of the session's own
    temporary payload cache immediately, while the session is still live --
    see the "burst_bytes_cache" note in `_run_async` for why this cannot be
    deferred to assembly-tick time. Bounded the same way the session's own
    `temporary_burst_payload` cache already is."""

    for candidate in candidates:
        if candidate.role != "high_resolution_burst" or candidate.media_asset_id in cache:
            continue
        content_hash = dict(candidate.quality_facts).get("content_hash")
        if not isinstance(content_hash, str):
            continue
        payload = session.temporary_burst_payload(content_hash)
        if not payload:
            continue
        cache[candidate.media_asset_id] = payload
        while len(cache) > _MAX_CACHED_BURST_BYTES:
            cache.pop(next(iter(cache)))


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
    ) -> None:
        self._repository_factory = repository_factory
        self._provider_loader = provider_loader
        self._transport_factory = transport_factory
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
            session = _EngineSession(
                stream_id=stream_id,
                playback_config=playback_config,
                provider_config_path=resolve_provider_config_path(provider_config_path),
                privacy_ignore_regions=privacy_ignore_regions,
                repository_factory=self._repository_factory,
                provider_loader=self._provider_loader,
                transport_factory=self._transport_factory,
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

    def stop_all(self, *, reason: str = "app_shutdown") -> None:
        with self._lock:
            sessions = list(self._sessions.values())
        for session in sessions:
            session.stop(reason=reason)
