"""Unified Observation panel contract (MockingBird Unified Observation
Experience v1): one product-facing Start/Stop/Health contract shared by
every currently-supported Stream type. `mockingbird.observation.
unified_status` is a pure composition layer over already-produced facts
from the existing, unchanged runtimes -- it starts nothing itself and
invents no new detector, tracker, or evidence-quality threshold.

Lane resolution mirrors actual repository capability exactly:

- ``camera_node`` Sources use the accepted frame-driven Observation Engine
  (`mockingbird.observation.engine_runtime`), unchanged.
- Streams whose `live_stream_type` is one of the existing backend-owned
  live-video kinds (RTSP, Linux local USB, Windows DirectShow) use the
  existing durable monitoring policy/runtime-status/camera-health path
  (`LiveCameraSessionManager` + `DurableMonitoringSupervisor`), unchanged.
- Remaining `external_url` Sources use the existing Snapshot Source
  monitor (`SourceMonitorManager`), unchanged.
- Everything else (demo, manual media, folder/webhook import, and
  not-yet-implemented future adapters) honestly reports no observation
  runtime rather than scaffolding fake support.
"""

from __future__ import annotations

from datetime import UTC, datetime

from mockingbird.api.schemas import (
    CameraHealthState,
    CameraHealthSummary,
    SourceMonitorStatusResponse,
    StreamMonitoringMode,
    StreamMonitoringPolicyResponse,
    StreamPlaybackKind,
    StreamPlaybackStatus,
    StreamPlaybackStatusValue,
    StreamRuntimeState,
    StreamRuntimeStatusResponse,
)
from mockingbird.observation import unified_status
from mockingbird.observation.engine_runtime import ObservationEngineCounts, ObservationEngineSessionStatus
from mockingbird.repository.product_repository import StreamLivePlaybackConfig

STREAM_ID = "stream-backyard-feeder"
SOURCE_ID = "source-backyard-demo"


def _playback(
    *,
    status: StreamPlaybackStatusValue = StreamPlaybackStatusValue.live_ready,
    message: str = "Ready.",
    kind: StreamPlaybackKind = StreamPlaybackKind.rtsp,
) -> StreamPlaybackStatus:
    return StreamPlaybackStatus(
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        status=status,
        playback_kind=kind,
        display_title="Backyard feeder",
        message=message,
        supports_zone_editing=True,
        supports_live_playback=status == StreamPlaybackStatusValue.live_ready,
    )


def _camera_node_config(**overrides: object) -> StreamLivePlaybackConfig:
    values: dict[str, object] = dict(
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        provider_key="camera_node",
        live_stream_url=None,
        live_stream_type="camera_node",
        camera_node_base_address="http://192.168.1.50:8787",
        camera_node_credential="fixture-credential",
        camera_node_camera_id="cam-1",
        camera_node_id="node-1",
        camera_node_evidence_profile_id="evidence-profile",
    )
    values.update(overrides)
    return StreamLivePlaybackConfig(**values)


def _rtsp_config() -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        provider_key="external_url",
        live_stream_url="rtsp://camera.local/live",
        live_stream_type="rtsp",
    )


def _local_usb_config() -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        provider_key="local_usb",
        live_stream_url=None,
        live_stream_type="local_usb",
        local_camera_device="/dev/video0",
    )


def _windows_dshow_config() -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        provider_key="local_usb",
        live_stream_url=None,
        live_stream_type="windows_dshow",
        windows_camera_name="EMEET SmartCam S600",
    )


def _external_url_snapshot_config() -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        provider_key="external_url",
        live_stream_url=None,
        live_stream_type="unknown",
    )


def _manual_media_config() -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        provider_key="manual_media",
        live_stream_url=None,
        live_stream_type="unknown",
    )


def _demo_config() -> StreamLivePlaybackConfig:
    return StreamLivePlaybackConfig(
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        provider_key=None,
        live_stream_url=None,
        live_stream_type="unknown",
    )


# --- Lane resolution: actual repository capability, not invented support ---


def test_camera_node_provider_resolves_to_camera_node_engine() -> None:
    assert (
        unified_status.resolve_observation_runtime(_camera_node_config())
        == unified_status.RUNTIME_KIND_CAMERA_NODE
    )


def test_rtsp_live_stream_type_resolves_to_live_monitoring() -> None:
    assert (
        unified_status.resolve_observation_runtime(_rtsp_config())
        == unified_status.RUNTIME_KIND_LIVE_MONITORING
    )


def test_local_usb_resolves_to_live_monitoring() -> None:
    assert (
        unified_status.resolve_observation_runtime(_local_usb_config())
        == unified_status.RUNTIME_KIND_LIVE_MONITORING
    )


def test_windows_dshow_resolves_to_live_monitoring() -> None:
    assert (
        unified_status.resolve_observation_runtime(_windows_dshow_config())
        == unified_status.RUNTIME_KIND_LIVE_MONITORING
    )


def test_plain_external_url_resolves_to_snapshot_monitor() -> None:
    assert (
        unified_status.resolve_observation_runtime(_external_url_snapshot_config())
        == unified_status.RUNTIME_KIND_SNAPSHOT_MONITOR
    )


def test_manual_media_resolves_to_unavailable() -> None:
    assert (
        unified_status.resolve_observation_runtime(_manual_media_config())
        == unified_status.RUNTIME_KIND_UNAVAILABLE
    )


def test_unconfigured_provider_resolves_to_unavailable() -> None:
    assert (
        unified_status.resolve_observation_runtime(_demo_config())
        == unified_status.RUNTIME_KIND_UNAVAILABLE
    )


# --- Support matrix: honest, code-grounded, no invented support ---


def test_support_matrix_reports_implemented_providers_as_supported() -> None:
    assert unified_status.provider_support_level("camera_node") == "observation_supported"
    assert unified_status.provider_support_level("local_usb") == "observation_supported"
    assert unified_status.provider_support_level("external_url") == "observation_supported"


def test_support_matrix_reports_demo_as_development_only() -> None:
    assert unified_status.provider_support_level("demo") == "development_only"


def test_support_matrix_reports_import_only_providers_as_unavailable() -> None:
    for provider_key in ("manual_media", "folder_import_future", "webhook_future"):
        assert unified_status.provider_support_level(provider_key) == "observation_unavailable"


def test_support_matrix_defaults_unknown_provider_to_unavailable() -> None:
    assert unified_status.provider_support_level(None) == "observation_unavailable"
    assert unified_status.provider_support_level("not_a_real_provider") == "observation_unavailable"


# --- Camera Node lane: preserve accepted engine behavior, add pre-start health ---


def test_camera_node_never_started_and_paired_reports_ready_stopped() -> None:
    facts = unified_status.camera_node_facts(
        session_status=None,
        config=_camera_node_config(),
        playback=_playback(status=StreamPlaybackStatusValue.live_ready, kind=StreamPlaybackKind.camera_node),
    )
    assert facts.state == "stopped"
    assert facts.observing is False
    assert facts.camera_connected is True
    assert facts.runtime_available is True
    assert facts.setup_action is None


def test_camera_node_never_started_with_stale_last_seen_reports_offline() -> None:
    """Boot Identity + Autonomous Recovery v1: "paired/configured !=
    live/reachable" -- once a real last-seen fact exists and has gone
    stale, configuration completeness alone must not report
    `camera_connected=True`. See "Host-side state" in
    docs/camera-node-installer-design.md."""

    now = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)
    last_seen = datetime(2026, 8, 21, 11, 0, 0, tzinfo=UTC)  # 60 minutes stale
    facts = unified_status.camera_node_facts(
        session_status=None,
        config=_camera_node_config(camera_node_last_seen_at=last_seen),
        playback=_playback(status=StreamPlaybackStatusValue.live_ready, kind=StreamPlaybackKind.camera_node),
        now=now,
    )
    assert facts.state == "stopped"  # Start remains the correct recovery action, never "reconfigure"
    assert facts.observing is False
    assert facts.camera_connected is False
    assert facts.setup_action is None
    assert "offline" in facts.camera_message.lower()
    assert "60 minute" in facts.camera_message


def test_camera_node_never_started_with_fresh_last_seen_reports_connected() -> None:
    now = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)
    last_seen = datetime(2026, 8, 21, 11, 58, 0, tzinfo=UTC)  # 2 minutes ago, well inside the threshold
    facts = unified_status.camera_node_facts(
        session_status=None,
        config=_camera_node_config(camera_node_last_seen_at=last_seen),
        playback=_playback(status=StreamPlaybackStatusValue.live_ready, kind=StreamPlaybackKind.camera_node),
        now=now,
    )
    assert facts.camera_connected is True
    assert facts.camera_message == "Camera Node is paired and ready."


def test_camera_node_never_started_with_no_last_seen_fact_keeps_prior_optimistic_default() -> None:
    """A Source with no last-seen fact at all (predates this milestone, or
    a pairing that just completed) is neither confirmed reachable nor
    confirmed offline -- a deliberate, disclosed scope boundary, not an
    oversight. See docs/camera-node-installer-design.md."""

    facts = unified_status.camera_node_facts(
        session_status=None,
        config=_camera_node_config(camera_node_last_seen_at=None),
        playback=_playback(status=StreamPlaybackStatusValue.live_ready, kind=StreamPlaybackKind.camera_node),
    )
    assert facts.camera_connected is True


def test_camera_node_never_started_and_unpaired_reports_needs_attention() -> None:
    facts = unified_status.camera_node_facts(
        session_status=None,
        config=_camera_node_config(camera_node_credential=None),
        playback=_playback(status=StreamPlaybackStatusValue.not_configured, kind=StreamPlaybackKind.camera_node),
    )
    assert facts.state == "needs_attention"
    assert facts.camera_connected is False
    assert facts.runtime_available is True
    assert facts.setup_action == "edit_camera_setup"
    assert "Camera Node" in facts.camera_message


def test_camera_node_running_session_passes_through_observing_state() -> None:
    session_status = ObservationEngineSessionStatus(
        stream_id=STREAM_ID,
        state="observing",
        observing=True,
        message="MockingBird is watching this camera for wildlife.",
        camera_connected=True,
        camera_message="Connected to the Camera Node.",
        engine_available=True,
        engine_message="Observation Engine is running.",
        started_at=datetime(2026, 8, 8, 12, 0, tzinfo=UTC),
        counts=ObservationEngineCounts(track_updates_observed=3, candidates_created=1),
        advanced={"provider_key": "frame-driven-onnx-cuda"},
    )
    facts = unified_status.camera_node_facts(
        session_status=session_status, config=_camera_node_config(), playback=_playback(kind=StreamPlaybackKind.camera_node),
    )
    assert facts.state == "observing"
    assert facts.observing is True
    assert facts.counts.candidates_created == 1
    assert facts.advanced["runtime_kind"] == unified_status.RUNTIME_KIND_CAMERA_NODE
    # Advanced-only vocabulary must never leak into the basic fields.
    assert "frame-driven-onnx-cuda" not in facts.message
    assert "frame-driven-onnx-cuda" not in facts.camera_message


def test_camera_node_engine_error_state_maps_to_needs_attention_not_error() -> None:
    session_status = ObservationEngineSessionStatus(
        stream_id=STREAM_ID,
        state="error",
        observing=False,
        message="Camera Node connection stopped: node_unavailable.",
        camera_connected=False,
        camera_message="Camera Node connection stopped: node_unavailable.",
        engine_available=True,
        engine_message="Observation Engine is running.",
    )
    facts = unified_status.camera_node_facts(
        session_status=session_status, config=_camera_node_config(), playback=_playback(kind=StreamPlaybackKind.camera_node),
    )
    assert facts.state == "needs_attention"
    assert facts.setup_action == "edit_camera_setup"


# --- Live monitoring lane (RTSP / local USB / Windows DirectShow) ---


def _policy(mode: StreamMonitoringMode) -> StreamMonitoringPolicyResponse:
    return StreamMonitoringPolicyResponse(
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        mode=mode,
        auto_create_review_candidates=False,
        evaluation_interval_seconds=10,
        quiet_period_seconds=30,
        minimum_detection_count=1,
        policy_revision=1,
        persisted=True,
        message="",
    )


def _runtime_status(
    actual_state: StreamRuntimeState, *, failure_code: str | None = None,
) -> StreamRuntimeStatusResponse:
    return StreamRuntimeStatusResponse(
        stream_id=STREAM_ID,
        source_id=SOURCE_ID,
        desired_mode=StreamMonitoringMode.armed,
        actual_state=actual_state,
        observed_policy_revision=1,
        checkpoint_present=True,
        active_session_count=1 if actual_state in {StreamRuntimeState.starting, StreamRuntimeState.running} else 0,
        failure_code=failure_code,
        consecutive_failure_count=0,
        last_stop_reason=None,
        message="runtime message",
    )


def _health(state: CameraHealthState, *, message: str = "health message") -> CameraHealthSummary:
    return CameraHealthSummary(
        stream_id=STREAM_ID,
        stream_name="Backyard feeder",
        source_id=SOURCE_ID,
        source_name="Backyard demo",
        state=state,
        message=message,
        desired_mode=StreamMonitoringMode.armed,
        actual_state=StreamRuntimeState.running,
        readiness_status=StreamPlaybackStatusValue.live_ready,
    )


def test_live_monitoring_off_and_ready_reports_stopped_healthy() -> None:
    facts = unified_status.live_monitoring_facts(
        policy=_policy(StreamMonitoringMode.off),
        runtime=_runtime_status(StreamRuntimeState.stopped),
        health=_health(CameraHealthState.stopped),
        playback=_playback(status=StreamPlaybackStatusValue.live_ready),
    )
    assert facts.state == "stopped"
    assert facts.camera_connected is True
    assert facts.runtime_available is True


def test_live_monitoring_off_and_unready_reports_needs_attention() -> None:
    facts = unified_status.live_monitoring_facts(
        policy=_policy(StreamMonitoringMode.off),
        runtime=_runtime_status(StreamRuntimeState.stopped),
        health=_health(CameraHealthState.stopped),
        playback=_playback(
            status=StreamPlaybackStatusValue.unsupported_rtsp_bridge_required,
            message="RTSP bridge unavailable - ffmpeg not found.",
        ),
    )
    assert facts.state == "needs_attention"
    assert facts.camera_connected is False
    assert facts.setup_action == "edit_camera_setup"
    assert "ffmpeg" in facts.message


def test_live_monitoring_armed_running_reports_observing() -> None:
    facts = unified_status.live_monitoring_facts(
        policy=_policy(StreamMonitoringMode.armed),
        runtime=_runtime_status(StreamRuntimeState.running),
        health=_health(CameraHealthState.healthy, message="Monitoring is running and recently received a usable frame."),
        playback=_playback(status=StreamPlaybackStatusValue.live_ready),
    )
    assert facts.state == "observing"
    assert facts.observing is True
    assert facts.camera_connected is True


def test_live_monitoring_armed_blocked_reports_needs_attention_with_retry() -> None:
    facts = unified_status.live_monitoring_facts(
        policy=_policy(StreamMonitoringMode.armed),
        runtime=_runtime_status(StreamRuntimeState.blocked, failure_code="camera_unavailable"),
        health=_health(CameraHealthState.camera_unavailable, message="The camera is unavailable after bounded recovery attempts."),
        playback=_playback(status=StreamPlaybackStatusValue.live_ready),
    )
    assert facts.state == "needs_attention"
    assert facts.retry_action is True
    assert "unavailable" in facts.camera_message.lower()


def test_live_monitoring_armed_starting_reports_starting() -> None:
    facts = unified_status.live_monitoring_facts(
        policy=_policy(StreamMonitoringMode.armed),
        runtime=_runtime_status(StreamRuntimeState.starting),
        health=_health(CameraHealthState.starting, message="Monitoring is starting and waiting for its first usable frame."),
        playback=_playback(status=StreamPlaybackStatusValue.live_ready),
    )
    assert facts.state == "starting"
    assert facts.observing is False


def test_live_monitoring_armed_interrupted_reports_starting_not_needs_attention() -> None:
    """Camera / Source + Multi-Camera Maturity v1, Phase F: a previous app
    instance ending without a clean stop is a calm, expected recovery-in-
    progress fact (durable-camera-monitor-lifecycle-design.md) -- it must
    read the same as the ordinary `stopped`-armed-but-not-yet-reconciled
    case above, never fall through to the generic needs_attention bucket
    a genuine failure uses."""

    facts = unified_status.live_monitoring_facts(
        policy=_policy(StreamMonitoringMode.armed),
        runtime=_runtime_status(StreamRuntimeState.interrupted),
        health=_health(CameraHealthState.starting, message="Monitoring is enabled and awaiting local supervision."),
        playback=_playback(status=StreamPlaybackStatusValue.live_ready),
    )
    assert facts.state == "starting"
    assert facts.observing is False


# --- Snapshot monitor lane (external_url still-image polling) ---


def _monitor_response(status: str, **overrides: object) -> SourceMonitorStatusResponse:
    values: dict[str, object] = dict(
        monitor_id="source-monitor-abc",
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        status=status,
        interval_seconds=15,
        max_runtime_seconds=1800,
        max_snapshots=100,
        snapshots_attempted=0,
        snapshots_saved=0,
        motion_checks_run=0,
        consecutive_failures=0,
        message="Monitoring is active.",
    )
    values.update(overrides)
    return SourceMonitorStatusResponse(**values)


def test_snapshot_monitor_never_started_and_configured_reports_stopped_ready() -> None:
    facts = unified_status.snapshot_monitor_facts(
        monitor=None, url_configured=True, playback=_playback(status=StreamPlaybackStatusValue.needs_stream_url),
    )
    assert facts.state == "stopped"
    assert facts.camera_connected is True
    assert facts.runtime_available is True


def test_snapshot_monitor_never_started_and_unconfigured_reports_needs_attention() -> None:
    facts = unified_status.snapshot_monitor_facts(
        monitor=None, url_configured=False, playback=_playback(status=StreamPlaybackStatusValue.needs_stream_url),
    )
    assert facts.state == "needs_attention"
    assert facts.setup_action == "edit_camera_setup"


def test_snapshot_monitor_running_reports_observing() -> None:
    facts = unified_status.snapshot_monitor_facts(
        monitor=_monitor_response("monitoring", last_activity_detected=False),
        url_configured=True,
        playback=_playback(status=StreamPlaybackStatusValue.needs_stream_url),
    )
    assert facts.state == "observing"
    assert facts.observing is True


def test_snapshot_monitor_error_reports_needs_attention() -> None:
    facts = unified_status.snapshot_monitor_facts(
        monitor=_monitor_response("error", last_error="Snapshot capture failed."),
        url_configured=True,
        playback=_playback(status=StreamPlaybackStatusValue.needs_stream_url),
    )
    assert facts.state == "needs_attention"


# --- Unavailable lane: honest, not scaffolded ---


def test_unavailable_lane_never_claims_it_can_observe() -> None:
    facts = unified_status.unavailable_facts(
        config=_manual_media_config(), playback=_playback(status=StreamPlaybackStatusValue.not_configured, message="manual media message"),
    )
    assert facts.runtime_available is False
    assert facts.observing is False
    assert facts.state == "stopped"


def test_unavailable_lane_carries_no_internal_vocabulary() -> None:
    facts = unified_status.unavailable_facts(config=_demo_config(), playback=_playback(status=StreamPlaybackStatusValue.demo))
    for forbidden in ("SnapshotObservationProvider", "ONNX", "CUDA", "policy_revision", "provider generation"):
        assert forbidden not in facts.message
        assert forbidden not in facts.camera_message
