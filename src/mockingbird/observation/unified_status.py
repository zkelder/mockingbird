"""Unified Observation panel composition (Unified Observation Experience v1).

Product Vertical Slice v1 made Start/Stop observing reachable from the app
for paired Camera Node Streams only, through `engine_runtime.
ObservationEngineSessionManager`. This module is the seam that lets every
other currently-supported Stream type present through that same basic
product contract (state/observing/message/camera health/failure reason)
while continuing to run on its own existing, unmodified runtime:

- ``camera_node`` Sources keep using the accepted frame-driven Observation
  Engine (`engine_runtime.ObservationEngineSessionManager`), unchanged.
- Streams configured with an existing backend-owned live-video kind (RTSP,
  Linux local USB, Windows DirectShow) keep using the existing durable
  monitoring policy / runtime-status / camera-health path
  (`LiveCameraSessionManager` + `DurableMonitoringSupervisor`), unchanged.
- Remaining ``external_url`` Sources keep using the existing Snapshot
  Source monitor (`SourceMonitorManager`), unchanged.
- Every other Source (demo, manual media, folder/webhook import, and any
  not-yet-implemented future adapter) honestly reports no observation
  runtime instead of scaffolding fake support.

Every function here is pure: it only reads already-produced facts passed
in by the caller and never touches a camera, model, database, or network
socket itself. It adds no new detector, tracker, evidence-quality
threshold, or candidate authority -- it only normalizes vocabulary and
picks which existing runtime's facts to present.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from mockingbird.api.schemas import (
    CameraHealthState,
    CameraHealthSummary,
    SourceMonitorStatusResponse,
    StreamMonitoringMode,
    StreamMonitoringPolicyResponse,
    StreamPlaybackStatus,
    StreamPlaybackStatusValue,
    StreamRuntimeState,
    StreamRuntimeStatusResponse,
)
from mockingbird.observation.engine_runtime import ObservationEngineCounts, ObservationEngineSessionStatus
from mockingbird.playback.local_camera_bridge import LOCAL_USB_STREAM_TYPE
from mockingbird.playback.windows_camera_bridge import WINDOWS_DSHOW_STREAM_TYPE
from mockingbird.repository.product_repository import StreamLivePlaybackConfig

RUNTIME_KIND_CAMERA_NODE = "camera_node_engine"
RUNTIME_KIND_LIVE_MONITORING = "live_monitoring"
RUNTIME_KIND_SNAPSHOT_MONITOR = "snapshot_monitor"
RUNTIME_KIND_UNAVAILABLE = "unavailable"

ObservationRuntimeKind = Literal[
    "camera_node_engine", "live_monitoring", "snapshot_monitor", "unavailable",
]

# The existing backend-owned live-video kinds `LiveCameraSessionManager`
# already supports (`live_camera_session.SUPPORTED_SESSION_TYPES` minus
# `camera_node`, which is routed to the dedicated engine lane instead so a
# paired Camera Node always uses the accepted frame-driven engine).
LIVE_MONITORING_STREAM_TYPES = frozenset({"rtsp", LOCAL_USB_STREAM_TYPE, WINDOWS_DSHOW_STREAM_TYPE})

ProviderSupportLevel = Literal[
    "observation_supported", "observation_setup_required", "observation_unavailable", "development_only",
]

# Boot Identity + Autonomous Recovery v1: shared with
# `mockingbird.diagnostics.doctor` (which imports this constant rather than
# keeping its own copy) so "how long since last contact before this stops
# reading as normal and starts reading as offline" is one judgment call,
# not two independently-tuned thresholds. Comfortably longer than both the
# ~45s normal exposure-checkpoint cadence (Today Coverage Truth v1) and the
# default bounded reconnect budget (6 attempts x 12s backoff = ~72s -- see
# `AnalysisStreamRetryPolicy`), so an ordinary, already-recovering
# reconnect never reads as "offline." Originally established by Camera Node
# Connectivity & Recovery Diagnosis v1 for Doctor's own open-interval
# staleness check; reused here unchanged for the same judgment applied to
# the durable last-seen fact instead.
CAMERA_NODE_LAST_SEEN_STALE_AFTER_SECONDS = 300.0

# Grounds the product support-matrix report in actual repository capability
# (see `source-provider-configuration-contract.md`'s provider-definition
# list) rather than asserting support that does not exist. `local_usb` and
# `external_url` are dual-purpose: the concrete lane a given Stream lands on
# still depends on its own configured `live_stream_type` (see
# `resolve_observation_runtime`), but the provider itself already has a
# working observation path either way.
PROVIDER_SUPPORT_MATRIX: dict[str, ProviderSupportLevel] = {
    "camera_node": "observation_supported",
    "local_usb": "observation_supported",
    "external_url": "observation_supported",
    "demo": "development_only",
    "manual_media": "observation_unavailable",
    "folder_import_future": "observation_unavailable",
    "webhook_future": "observation_unavailable",
    # Registered as a future Add Camera contract only; a real RTSP Stream is
    # actually configured through `external_url` + `live_stream_type=rtsp`
    # (see `resolve_observation_runtime`), which already reports supported.
    "rtsp_future": "observation_unavailable",
    "esp32_future": "observation_unavailable",
    "browser_camera_future": "observation_unavailable",
}


def provider_support_level(provider_key: str | None) -> ProviderSupportLevel:
    """Honest, code-grounded provider classification for the support-matrix
    report. Never invents a support level a provider does not actually have."""

    return PROVIDER_SUPPORT_MATRIX.get(provider_key or "", "observation_unavailable")


def resolve_observation_runtime(config: StreamLivePlaybackConfig) -> ObservationRuntimeKind:
    """Pick the one existing runtime lane this Stream's Start/Stop/Health
    action should reuse. A Camera Node Stream always uses the accepted
    engine even though `LiveCameraSessionManager` could technically also
    monitor it (the hard architecture rule: do not force every camera type
    through the frame-driven engine, but do route the Camera Node type that
    engine was built for through it)."""

    if config.provider_key == "camera_node":
        return RUNTIME_KIND_CAMERA_NODE
    if config.live_stream_type in LIVE_MONITORING_STREAM_TYPES:
        return RUNTIME_KIND_LIVE_MONITORING
    if config.provider_key == "external_url":
        return RUNTIME_KIND_SNAPSHOT_MONITOR
    return RUNTIME_KIND_UNAVAILABLE


@dataclass(frozen=True)
class ObservationPanelFacts:
    """The unified product contract's fields, provider-neutral. Mirrors
    `ObservationSessionStatusResponse` field-for-field so the API layer can
    wrap this directly; kept as a plain dataclass here so this module never
    depends on FastAPI routing."""

    state: Literal["stopped", "starting", "observing", "stopping", "needs_attention"]
    observing: bool
    message: str
    camera_connected: bool
    camera_message: str
    engine_available: bool
    engine_message: str
    runtime_available: bool = True
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    stopped_reason: str | None = None
    last_candidate_visit_id: str | None = None
    last_useful_frame_at: datetime | None = None
    setup_action: Literal["edit_camera_setup"] | None = None
    retry_action: bool = False
    # Visit Authority Budget + Ambiguous-Boundary Recall Closure v1: `False`/
    # `None` for every lane except the Camera Node engine lane while its own
    # in-session candidate budget is genuinely exhausted -- see
    # `ObservationEngineSessionStatus`'s matching fields.
    candidate_authority_exhausted: bool = False
    candidate_authority_message: str | None = None
    counts: ObservationEngineCounts = field(default_factory=ObservationEngineCounts)
    advanced: dict[str, object] = field(default_factory=dict)


_NOT_A_PAIRED_CAMERA_NODE_MESSAGE = (
    "This camera isn't a paired MockingBird Camera Node yet. Pair a Camera "
    "Node in Add Camera to use wildlife observation here."
)


def _camera_node_paired(config: StreamLivePlaybackConfig) -> bool:
    """Mirrors `engine_runtime._EngineSession._run_async`'s own pairing
    guard exactly, so the pre-start health check and the engine's own
    honest "not paired" outcome never disagree."""

    return bool(
        config.provider_key == "camera_node"
        and config.camera_node_base_address
        and config.camera_node_credential
        and config.camera_node_camera_id
        and config.camera_node_evidence_profile_id
    )


def camera_node_facts(
    *,
    session_status: ObservationEngineSessionStatus | None,
    config: StreamLivePlaybackConfig,
    playback: StreamPlaybackStatus | None,
    now: datetime | None = None,
) -> ObservationPanelFacts:
    """Camera Node lane: pass the accepted engine's own session status
    through unchanged (only its wire-level state name is normalized to the
    unified vocabulary); before a session ever starts, report a real
    pairing-based health fact instead of a generic placeholder, still
    without starting anything.

    Boot Identity + Autonomous Recovery v1: "no session currently running"
    previously reported `camera_connected=True` from configuration
    completeness alone -- exactly the "paired/configured != live/reachable"
    violation named in docs/camera-node-installer-design.md. This function
    stays pure/side-effect-free (see the module docstring) -- `now` and
    `config.camera_node_last_seen_at` are both already-resolved facts the
    caller supplies, never a live probe from here."""

    if session_status is not None:
        wire_state = "needs_attention" if session_status.state == "error" else session_status.state
        setup_action = (
            "edit_camera_setup"
            if wire_state == "needs_attention" and not session_status.camera_connected
            else None
        )
        return ObservationPanelFacts(
            state=wire_state,
            observing=session_status.observing,
            message=session_status.message,
            camera_connected=session_status.camera_connected,
            camera_message=session_status.camera_message,
            engine_available=session_status.engine_available,
            engine_message=session_status.engine_message,
            runtime_available=True,
            started_at=session_status.started_at,
            stopped_at=session_status.stopped_at,
            stopped_reason=session_status.stopped_reason,
            last_candidate_visit_id=session_status.last_candidate_visit_id,
            setup_action=setup_action,
            candidate_authority_exhausted=session_status.candidate_authority_exhausted,
            candidate_authority_message=session_status.candidate_authority_message,
            counts=session_status.counts,
            advanced={**session_status.advanced, "runtime_kind": RUNTIME_KIND_CAMERA_NODE},
        )

    paired = _camera_node_paired(config)
    ready = paired and playback is not None and playback.status == StreamPlaybackStatusValue.live_ready
    if ready:
        last_seen_at = config.camera_node_last_seen_at
        reference = now or datetime.now(UTC)
        # `last_seen_at is None` means this Source has never yet had a
        # successful checkpoint since this fact started being tracked --
        # neither confirmed reachable nor confirmed offline. Rather than
        # guess, this keeps the pre-existing optimistic "paired and ready"
        # wording (a freshly-completed pairing itself just proved
        # reachability moments ago) -- a deliberate, disclosed scope
        # boundary; see docs/camera-node-installer-design.md. Once any real
        # contact has been recorded, staleness against it is authoritative.
        stale = (
            last_seen_at is not None
            and (reference - last_seen_at).total_seconds() > CAMERA_NODE_LAST_SEEN_STALE_AFTER_SECONDS
        )
        if stale:
            minutes = max(1, round((reference - last_seen_at).total_seconds() / 60))
            return ObservationPanelFacts(
                state="stopped",
                observing=False,
                message="Not observing.",
                camera_connected=False,
                camera_message=f"Camera Node offline -- last seen {minutes} minute(s) ago.",
                engine_available=False,
                engine_message="Observation Engine has not started yet.",
                runtime_available=True,
                advanced={"runtime_kind": RUNTIME_KIND_CAMERA_NODE},
            )
        return ObservationPanelFacts(
            state="stopped",
            observing=False,
            message="Not observing.",
            camera_connected=True,
            camera_message="Camera Node is paired and ready.",
            engine_available=False,
            engine_message="Observation Engine has not started yet.",
            runtime_available=True,
            advanced={"runtime_kind": RUNTIME_KIND_CAMERA_NODE},
        )
    reason = (
        _NOT_A_PAIRED_CAMERA_NODE_MESSAGE
        if not paired
        else (playback.message if playback is not None else "This camera is not ready yet.")
    )
    return ObservationPanelFacts(
        state="needs_attention",
        observing=False,
        message=reason,
        camera_connected=False,
        camera_message=reason,
        engine_available=False,
        engine_message="Observation Engine has not started yet.",
        runtime_available=True,
        setup_action="edit_camera_setup",
        advanced={"runtime_kind": RUNTIME_KIND_CAMERA_NODE},
    )


_LIVE_MONITORING_STATE_MAP: dict[str, str] = {
    StreamRuntimeState.starting.value: "starting",
    StreamRuntimeState.running.value: "observing",
    StreamRuntimeState.stopping.value: "stopping",
    # Armed but the supervisor has not reconciled it yet -- a transitional
    # fact, not a problem to alarm the user about.
    StreamRuntimeState.stopped.value: "starting",
}


def live_monitoring_facts(
    *,
    policy: StreamMonitoringPolicyResponse,
    runtime: StreamRuntimeStatusResponse,
    health: CameraHealthSummary,
    playback: StreamPlaybackStatus | None,
) -> ObservationPanelFacts:
    """Live-monitoring lane (RTSP / Linux local USB / Windows DirectShow):
    "Start observing" and "Stop observing" are the existing armed/off
    durable monitoring policy toggle; camera health reuses the existing,
    already-tested `CameraHealthSummary` narrative unchanged."""

    if policy.mode != StreamMonitoringMode.armed:
        ready = playback is not None and playback.status == StreamPlaybackStatusValue.live_ready
        if ready:
            return ObservationPanelFacts(
                state="stopped",
                observing=False,
                message="Not observing.",
                camera_connected=True,
                camera_message="Ready to observe.",
                engine_available=True,
                engine_message="Ready.",
                runtime_available=True,
                advanced={"runtime_kind": RUNTIME_KIND_LIVE_MONITORING, "desired_mode": policy.mode},
            )
        reason = playback.message if playback is not None else "This camera needs setup before observation can start."
        return ObservationPanelFacts(
            state="needs_attention",
            observing=False,
            message=reason,
            camera_connected=False,
            camera_message=reason,
            engine_available=False,
            engine_message="Observation is not available for this camera yet.",
            runtime_available=True,
            setup_action="edit_camera_setup",
            advanced={"runtime_kind": RUNTIME_KIND_LIVE_MONITORING, "desired_mode": policy.mode},
        )

    state = _LIVE_MONITORING_STATE_MAP.get(runtime.actual_state.value, "needs_attention")
    healthy = health.state == CameraHealthState.healthy
    setup_action = "edit_camera_setup" if health.state == CameraHealthState.setup_incomplete else None
    return ObservationPanelFacts(
        state=state,
        observing=state == "observing",
        message=health.message,
        camera_connected=healthy,
        camera_message=health.message,
        engine_available=True,
        engine_message="Ready.",
        runtime_available=True,
        last_useful_frame_at=health.last_good_frame_at,
        stopped_reason=runtime.last_stop_reason,
        setup_action=setup_action,
        retry_action=state == "needs_attention",
        advanced={
            "runtime_kind": RUNTIME_KIND_LIVE_MONITORING,
            "desired_mode": policy.mode,
            "actual_state": runtime.actual_state,
            "failure_code": runtime.failure_code,
        },
    )


_SNAPSHOT_MONITOR_STATE_MAP: dict[str, str] = {
    "starting": "starting",
    "monitoring": "observing",
    "stopped_by_user": "stopped",
    "completed": "stopped",
    "error": "needs_attention",
}


def snapshot_monitor_facts(
    *,
    monitor: SourceMonitorStatusResponse | None,
    url_configured: bool,
    playback: StreamPlaybackStatus | None,
) -> ObservationPanelFacts:
    """Snapshot-monitor lane (`external_url` still-image polling): reuses
    the existing Source monitor's own already-plain-language status
    message unchanged rather than re-deriving new copy."""

    del playback  # not needed once a real monitor message exists; kept for a uniform call shape
    if monitor is None or monitor.status == "stopped":
        if url_configured:
            return ObservationPanelFacts(
                state="stopped",
                observing=False,
                message="Not observing.",
                camera_connected=True,
                camera_message="Ready to observe.",
                engine_available=True,
                engine_message="Ready.",
                runtime_available=True,
                advanced={"runtime_kind": RUNTIME_KIND_SNAPSHOT_MONITOR},
            )
        reason = "Add an external URL before starting observation."
        return ObservationPanelFacts(
            state="needs_attention",
            observing=False,
            message=reason,
            camera_connected=False,
            camera_message=reason,
            engine_available=False,
            engine_message=reason,
            runtime_available=True,
            setup_action="edit_camera_setup",
            advanced={"runtime_kind": RUNTIME_KIND_SNAPSHOT_MONITOR},
        )

    state = _SNAPSHOT_MONITOR_STATE_MAP.get(monitor.status, "needs_attention")
    camera_connected = monitor.status in {"monitoring", "starting"} or (
        monitor.status in {"stopped_by_user", "completed"} and monitor.snapshots_saved > 0
    )
    last_useful_frame_at = monitor.last_tick_at if monitor.snapshots_saved > 0 else None
    return ObservationPanelFacts(
        state=state,
        observing=state == "observing",
        message=monitor.message,
        camera_connected=camera_connected,
        camera_message=monitor.message,
        engine_available=True,
        engine_message="Ready.",
        runtime_available=True,
        last_useful_frame_at=last_useful_frame_at,
        stopped_reason=monitor.stop_reason,
        advanced={"runtime_kind": RUNTIME_KIND_SNAPSHOT_MONITOR, "monitor_status": monitor.status},
    )


_DEFAULT_UNAVAILABLE_MESSAGE = "This Stream doesn't support automatic wildlife observation yet."


def unavailable_facts(
    *,
    config: StreamLivePlaybackConfig,
    playback: StreamPlaybackStatus | None,
) -> ObservationPanelFacts:
    """No integrated observation runtime exists for this Stream today.
    Reported calmly (`state="stopped"`, `runtime_available=False`) rather
    than as an alarming failure, and never with a Start action that would
    only fail -- an honest unavailable state, not scaffolded fake support."""

    reason = (playback.message if playback is not None else None) or _DEFAULT_UNAVAILABLE_MESSAGE
    return ObservationPanelFacts(
        state="stopped",
        observing=False,
        message=reason,
        camera_connected=False,
        camera_message=reason,
        engine_available=False,
        engine_message=reason,
        runtime_available=False,
        advanced={"runtime_kind": RUNTIME_KIND_UNAVAILABLE, "provider_key": config.provider_key},
    )
