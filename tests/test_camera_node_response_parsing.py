"""Camera Node response parsing: additive-compatibility fallbacks (First-
Hour Onboarding + Whole-Product Observability Closure v1, "C3").

Confirmed by this milestone's own compatibility inventory: before this fix,
a genuinely new enum value for `status`/`capture_profile_status.state`/
`orientation` in a Camera Node's own response -- for example a newer Node
paired to an older host -- hard-crashed the *entire* camera list with
`node_response_invalid`, rather than degrading gracefully for the one
unrecognized field. `capture_class` deliberately stays a hard requirement
(see `_capture_profiles`'s own comment) and is not covered here.
"""

from __future__ import annotations

import pytest

from mockingbird.source_providers.camera_node import (
    CameraNodeClientError,
    _camera_items,
    _capture_profile_status,
    _capture_profiles,
)


def _valid_camera_payload(**overrides: object) -> dict:
    payload = {
        "camera_id": "cam-0",
        "display_name": "Feeder camera",
        "status": "available",
    }
    payload.update(overrides)
    return payload


def test_camera_items_unrecognized_status_falls_back_to_unavailable_not_a_crash() -> None:
    cameras = _camera_items([_valid_camera_payload(status="future_status_value")])
    assert len(cameras) == 1
    assert cameras[0].status == "unavailable"


def test_camera_items_known_status_is_unchanged() -> None:
    cameras = _camera_items([_valid_camera_payload(status="setup_required")])
    assert cameras[0].status == "setup_required"


def test_camera_items_missing_required_field_still_raises() -> None:
    """Only the enum-value soft-fallback changed -- a genuinely malformed
    response (missing the camera's own identity) must still be refused."""

    with pytest.raises(CameraNodeClientError):
        _camera_items([{"camera_id": "cam-0", "display_name": "Feeder camera"}])


def _valid_profile_payload(**overrides: object) -> dict:
    payload = {
        "profile_id": "profile-0",
        "purposes": ["monitoring"],
        "width": 1920,
        "height": 1080,
        "max_expected_bytes": 500_000,
        "capture_class": "warm",
    }
    payload.update(overrides)
    return payload


def test_capture_profiles_unrecognized_orientation_falls_back_to_normal() -> None:
    profiles = _capture_profiles([_valid_profile_payload(orientation="rotate_45_future_value")])
    assert len(profiles) == 1
    assert profiles[0].orientation == "normal"


def test_capture_profiles_missing_orientation_defaults_to_normal_unchanged() -> None:
    profiles = _capture_profiles([_valid_profile_payload()])
    assert profiles[0].orientation == "normal"


def test_capture_profiles_known_orientation_is_unchanged() -> None:
    profiles = _capture_profiles([_valid_profile_payload(orientation="rotate_90")])
    assert profiles[0].orientation == "rotate_90"


def test_capture_profiles_unrecognized_capture_class_still_raises() -> None:
    """`capture_class` deliberately stays strict -- see the module's own
    comment on why (real downstream capture-behavior decisions, not
    presentational)."""

    with pytest.raises(CameraNodeClientError):
        _capture_profiles([_valid_profile_payload(capture_class="future_capture_class")])


def test_capture_profile_status_unrecognized_state_falls_back_to_untested() -> None:
    statuses = _capture_profile_status([{"profile_id": "profile-0", "state": "future_state_value"}])
    assert len(statuses) == 1
    assert statuses[0].state == "untested"


def test_capture_profile_status_known_state_is_unchanged() -> None:
    statuses = _capture_profile_status([{"profile_id": "profile-0", "state": "accepted"}])
    assert statuses[0].state == "accepted"


def test_capture_profile_status_missing_profile_id_still_raises() -> None:
    with pytest.raises(CameraNodeClientError):
        _capture_profile_status([{"state": "accepted"}])
