"""Host <-> Camera Node Release-Compatibility Preflight v1.

Tier 1: the pure decision table (`classify_node_compatibility`) needs no
network at all; the live orchestration (`probe_node_compatibility`) is
exercised against the exact same `CameraNodeClient(requester=...)`
injection seam `test_camera_node.py` already established and trusts for
this client -- a fake wire transport, real, unmodified production
`CameraNodeClient`/`estimate_rtt_clock_calibration` code underneath (see
Section 20 of the governing milestone brief: never a second calibration
implementation).

The `test_v8_reproducer_*` tests are the named Tier 1 reproducer Section 19
of the governing milestone brief requires: a Node whose `/node/v1/health`
response is byte-for-byte the same shape the real reference Camera Node
returned during Representative Daylight Gate A Field Acceptance v8 (no
`node_receive_time`/`node_time` at all) -- ordinary health remains fine,
but field-acceptance compatibility must fail, before any session starts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from itertools import cycle
import json

import pytest

from mockingbird.observation.clock_calibration import RttClockCalibrationRecord
from mockingbird.observation.node_compatibility import (
    REQUIRED_CAPABILITIES,
    classify_node_compatibility,
    probe_node_compatibility,
)
from mockingbird.source_providers.camera_node import CameraNodeClient

_BASE_ADDRESS = "http://127.0.0.1:8787"
_CAMERA_ID = "opaque-camera-1"
_CREDENTIAL = "test-credential"

# The exact real v8 payload shape (Representative Daylight Gate A Field
# Acceptance v8 report, "RTT calibration field proof": a live `/node/v1/
# health` response with no `node_receive_time`/`node_time` at all --
# ordinary health fields all present and valid).
_OLD_NODE_HEALTH = {
    "node_id": "node-real-reference",
    "display_name": "Reference Pi",
    "api_version": "v1",
    "status": "available",
    "camera_count": 1,
    "available_camera_count": 1,
    "service_version": "0.1.0",
}

_CAMERAS_ITEM = {
    "camera_id": _CAMERA_ID,
    "display_name": "Feeder view",
    "status": "available",
    "snapshot_supported": True,
}


class _FakeRequester:
    """Mirrors `test_camera_node.py`'s own `_FakeNodeRequester` seam
    exactly (`CameraNodeClient(requester=...)`) -- a controllable fake wire
    transport, never a second HTTP client implementation."""

    def __init__(
        self,
        *,
        health: dict[str, object] | None = _OLD_NODE_HEALTH,
        health_status: int = 200,
        cameras: list[dict[str, object]] | None = None,
        cameras_status: int = 200,
    ) -> None:
        self.health_body = health
        self.health_status = health_status
        self.cameras_items = cameras if cameras is not None else [_CAMERAS_ITEM]
        self.cameras_status = cameras_status

    def request(self, *, method, url, headers, body, max_bytes, timing):
        if url.endswith("/health"):
            payload = self.health_body if self.health_body is not None else {}
            return self.health_status, {"Content-Type": "application/json"}, json.dumps(payload).encode()
        if url.endswith("/cameras"):
            return (
                self.cameras_status,
                {"Content-Type": "application/json"},
                json.dumps({"items": self.cameras_items}).encode(),
            )
        return 404, {"Content-Type": "application/json"}, b"{}"


def _repeating_clock(ticks: list[datetime]) -> Callable[[], datetime]:
    return lambda cycled=cycle(ticks): next(cycled)


def _current_node_health(*, extra: dict[str, object] | None = None) -> dict[str, object]:
    payload = {
        **_OLD_NODE_HEALTH,
        "node_receive_time": "2026-09-01T00:00:00.005000+00:00",
        "node_time": "2026-09-01T00:00:00.015000+00:00",
    }
    if extra:
        payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Pure decision table
# ---------------------------------------------------------------------------


def _calibrated_record() -> RttClockCalibrationRecord:
    return RttClockCalibrationRecord(
        stream_id="s1", source_offset_ms=0, calibrated_at=datetime.now(UTC),
        sample_count=5, valid_sample_count=5, state="calibrated",
        offset_ms=10.0, offset_min_ms=8.0, offset_max_ms=12.0,
        uncertainty_ms=2.0, rtt_ms=20.0, node_processing_ms=10.0,
    )


def _insufficient_record() -> RttClockCalibrationRecord:
    return RttClockCalibrationRecord(
        stream_id="s1", source_offset_ms=0, calibrated_at=datetime.now(UTC),
        sample_count=5, valid_sample_count=0, state="insufficient_samples",
    )


@pytest.mark.parametrize("profile", ["ordinary_monitoring", "field_acceptance"])
def test_unreachable_node_is_never_compatible_for_any_profile(profile) -> None:
    state, reasons, missing = classify_node_compatibility(
        profile=profile, reachable=False, protocol_valid=False,
        camera_checked=False, camera_available=False,
        rtt_fields_present=False, rtt_calibration=None,
    )
    assert state == "node_unreachable"
    assert reasons
    assert missing == REQUIRED_CAPABILITIES[profile]


def test_malformed_protocol_response_is_incompatible_protocol_not_unreachable() -> None:
    state, _, _ = classify_node_compatibility(
        profile="field_acceptance", reachable=True, protocol_valid=False,
        camera_checked=False, camera_available=False,
        rtt_fields_present=False, rtt_calibration=None,
    )
    assert state == "incompatible_protocol"


def test_ordinary_monitoring_ignores_missing_rtt_capability() -> None:
    """Section 15/19: an old, pre-RTT Node must not become unnecessarily
    blocked from ordinary product operation."""

    state, reasons, missing = classify_node_compatibility(
        profile="ordinary_monitoring", reachable=True, protocol_valid=True,
        camera_checked=False, camera_available=False,
        rtt_fields_present=False, rtt_calibration=None,
    )
    assert state == "compatible"
    assert reasons == ()
    assert missing == ()


def test_ordinary_monitoring_ignores_camera_unavailability() -> None:
    """`expected_camera_available` is not in `ordinary_monitoring`'s own
    required-capability tuple -- this profile never even checks it."""

    state, _, _ = classify_node_compatibility(
        profile="ordinary_monitoring", reachable=True, protocol_valid=True,
        camera_checked=True, camera_available=False,
        rtt_fields_present=False, rtt_calibration=None,
    )
    assert state == "compatible"


def test_field_acceptance_v8_class_reproducer_is_incompatible_missing_capability() -> None:
    """The exact v8 root cause: health reachable and otherwise fine, RTT
    timestamp fields simply absent -- never `node_unreachable`, never a
    generic "Camera Node unhealthy" bucket (Section 11)."""

    state, reasons, missing = classify_node_compatibility(
        profile="field_acceptance", reachable=True, protocol_valid=True,
        camera_checked=True, camera_available=True,
        rtt_fields_present=False, rtt_calibration=None,
    )
    assert state == "incompatible_missing_capability"
    assert missing == ("rtt_timestamp_fields",)
    assert "too old" in reasons[0]


def test_field_acceptance_missing_camera_takes_priority_over_missing_rtt() -> None:
    state, _, missing = classify_node_compatibility(
        profile="field_acceptance", reachable=True, protocol_valid=True,
        camera_checked=True, camera_available=False,
        rtt_fields_present=False, rtt_calibration=None,
    )
    assert state == "camera_unavailable"
    assert missing == ("expected_camera_available",)


def test_field_acceptance_advertised_but_broken_calibration_is_distinct_state() -> None:
    """Fields present and advertised, but a real calibration attempt still
    failed -- must not be confused with the "fields absent" v8 case."""

    state, reasons, missing = classify_node_compatibility(
        profile="field_acceptance", reachable=True, protocol_valid=True,
        camera_checked=True, camera_available=True,
        rtt_fields_present=True, rtt_calibration=_insufficient_record(),
    )
    assert state == "calibration_failed"
    assert missing == ("bounded_rtt_clock_calibration",)
    assert "insufficient_samples" in reasons[0]


def test_field_acceptance_fully_compatible() -> None:
    state, reasons, missing = classify_node_compatibility(
        profile="field_acceptance", reachable=True, protocol_valid=True,
        camera_checked=True, camera_available=True,
        rtt_fields_present=True, rtt_calibration=_calibrated_record(),
    )
    assert state == "compatible"
    assert reasons == ()
    assert missing == ()


# ---------------------------------------------------------------------------
# Live orchestration (`probe_node_compatibility`), fake wire transport only
# ---------------------------------------------------------------------------


def test_probe_v8_reproducer_old_node_fails_field_acceptance_before_any_session() -> None:
    client = CameraNodeClient(requester=_FakeRequester(health=_OLD_NODE_HEALTH))
    result = probe_node_compatibility(
        client, stream_id="s1", profile="field_acceptance", base_address=_BASE_ADDRESS,
        credential=_CREDENTIAL, expected_camera_id=_CAMERA_ID, host_app_version="0.1.0",
    )
    assert result.state == "incompatible_missing_capability"
    assert result.compatible is False
    assert result.node_reachable is True
    assert result.rtt_calibration is None, "no real batch should be spent once fields are already absent"
    assert "rtt_timestamp_fields" in result.missing_capabilities
    assert "Upgrade the Camera Node" in result.message


def test_probe_v8_reproducer_old_node_still_passes_ordinary_monitoring() -> None:
    """Backward compatibility (Section 15/19): the identical old-Node
    response remains fully usable for everyday product operation."""

    client = CameraNodeClient(requester=_FakeRequester(health=_OLD_NODE_HEALTH))
    result = probe_node_compatibility(
        client, stream_id="s1", profile="ordinary_monitoring", base_address=_BASE_ADDRESS,
        host_app_version="0.1.0",
    )
    assert result.state == "compatible"
    assert result.compatible is True


def test_probe_old_node_response_parses_cleanly_never_raises() -> None:
    """Absence of new metadata means capability unavailable, never a
    parser failure (Section 18)."""

    client = CameraNodeClient(requester=_FakeRequester(health=_OLD_NODE_HEALTH))
    result = probe_node_compatibility(
        client, stream_id="s1", profile="field_acceptance", base_address=_BASE_ADDRESS,
        credential=_CREDENTIAL, expected_camera_id=_CAMERA_ID, host_app_version="0.1.0",
    )
    assert result.node_api_version == "v1"
    assert result.node_service_version == "0.1.0"


def test_probe_current_node_with_valid_batch_is_compatible() -> None:
    ticks = [
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 9, 1, tzinfo=UTC) + timedelta(milliseconds=20),
    ]
    client = CameraNodeClient(requester=_FakeRequester(health=_current_node_health()))
    result = probe_node_compatibility(
        client, stream_id="s1", profile="field_acceptance", base_address=_BASE_ADDRESS,
        credential=_CREDENTIAL, expected_camera_id=_CAMERA_ID, host_app_version="0.1.0",
        rtt_batch_size=5, clock=_repeating_clock(ticks),
    )
    assert result.state == "compatible"
    assert result.compatible is True
    assert result.rtt_calibration is not None
    assert result.rtt_calibration.state == "calibrated"
    assert result.missing_capabilities == ()
    assert result.observed_capabilities == REQUIRED_CAPABILITIES["field_acceptance"]


def test_probe_advertised_but_broken_calibration_fails_despite_present_fields() -> None:
    """Fields present/advertised, but every real round trip exceeds the
    accepted maximum RTT -- `insufficient_samples`, not `compatible`."""

    ticks = [
        datetime(2026, 9, 1, tzinfo=UTC),
        datetime(2026, 9, 1, tzinfo=UTC) + timedelta(seconds=2),
    ]
    client = CameraNodeClient(requester=_FakeRequester(health=_current_node_health()))
    result = probe_node_compatibility(
        client, stream_id="s1", profile="field_acceptance", base_address=_BASE_ADDRESS,
        credential=_CREDENTIAL, expected_camera_id=_CAMERA_ID, host_app_version="0.1.0",
        rtt_batch_size=5, clock=_repeating_clock(ticks),
    )
    assert result.state == "calibration_failed"
    assert result.rtt_calibration is not None
    assert result.rtt_calibration.state == "insufficient_samples"


def test_probe_node_unreachable_is_a_distinct_state() -> None:
    client = CameraNodeClient(requester=_FakeRequester(health=_OLD_NODE_HEALTH, health_status=503))
    result = probe_node_compatibility(
        client, stream_id="s1", profile="field_acceptance", base_address=_BASE_ADDRESS,
        credential=_CREDENTIAL, expected_camera_id=_CAMERA_ID, host_app_version="0.1.0",
    )
    assert result.state == "node_unreachable"
    assert result.node_reachable is False
    assert result.rtt_calibration is None


def test_probe_camera_unavailable_is_a_distinct_state() -> None:
    client = CameraNodeClient(
        requester=_FakeRequester(health=_current_node_health(), cameras=[{**_CAMERAS_ITEM, "camera_id": "some-other-camera"}])
    )
    result = probe_node_compatibility(
        client, stream_id="s1", profile="field_acceptance", base_address=_BASE_ADDRESS,
        credential=_CREDENTIAL, expected_camera_id=_CAMERA_ID, host_app_version="0.1.0",
    )
    assert result.state == "camera_unavailable"
    assert result.camera_available is False
    assert result.rtt_calibration is None, "no real batch should be spent once the expected camera is already absent"


def test_probe_without_credential_skips_camera_check_instead_of_failing() -> None:
    """A caller with only a reachable `base_address` (Section 25's own
    ad hoc real-Node exercise, which has no paired credential) gets a real
    reachability/RTT verdict; `camera_available` is `None` (not checked),
    never `False` (checked and absent)."""

    ticks = [datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC) + timedelta(milliseconds=20)]
    client = CameraNodeClient(requester=_FakeRequester(health=_current_node_health()))
    result = probe_node_compatibility(
        client, stream_id="s1", profile="field_acceptance", base_address=_BASE_ADDRESS,
        host_app_version="0.1.0", rtt_batch_size=5, clock=_repeating_clock(ticks),
    )
    assert result.camera_available is None
    assert result.state == "compatible"


def test_probe_malformed_health_response_is_incompatible_protocol() -> None:
    client = CameraNodeClient(requester=_FakeRequester(health={"unexpected": "shape"}))
    result = probe_node_compatibility(
        client, stream_id="s1", profile="field_acceptance", base_address=_BASE_ADDRESS,
        credential=_CREDENTIAL, expected_camera_id=_CAMERA_ID, host_app_version="0.1.0",
    )
    assert result.state == "incompatible_protocol"


def test_probe_reports_host_and_node_identity_for_diagnostics() -> None:
    """Section 17/23: Node build identity is retained as diagnostic
    evidence, never the compatibility decision itself."""

    client = CameraNodeClient(requester=_FakeRequester(health=_current_node_health()))
    result = probe_node_compatibility(
        client, stream_id="s1", profile="ordinary_monitoring", base_address=_BASE_ADDRESS,
        host_app_version="0.1.0", host_git_commit="da1d05e",
    )
    assert result.host_app_version == "0.1.0"
    assert result.host_git_commit == "da1d05e"
    assert result.node_service_version == "0.1.0"
    assert result.version_skew_detected is False


def test_probe_flags_version_skew_only_as_informational_never_as_a_failure() -> None:
    """Section 24: differing build identity is reported, never a reason to
    fail an otherwise-compatible Node."""

    client = CameraNodeClient(
        requester=_FakeRequester(health=_current_node_health(extra={"service_version": "9.9.9"}))
    )
    ticks = [datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 1, tzinfo=UTC) + timedelta(milliseconds=20)]
    result = probe_node_compatibility(
        client, stream_id="s1", profile="field_acceptance", base_address=_BASE_ADDRESS,
        credential=_CREDENTIAL, expected_camera_id=_CAMERA_ID, host_app_version="0.1.0",
        rtt_batch_size=5, clock=_repeating_clock(ticks),
    )
    assert result.version_skew_detected is True
    assert result.compatible is True, "a detected version skew must never by itself flip compatibility"
