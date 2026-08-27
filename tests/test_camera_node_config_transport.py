"""Tier 1: Camera Node transport configuration surface (Phase A/F/G knobs)."""

from __future__ import annotations

import pytest

from mockingbird_node.config import CameraNodeConfig, normalize_host_base_address


def _clear_transport_env(monkeypatch) -> None:
    for name in (
        "MOCKINGBIRD_NODE_HOST_BASE_ADDRESS",
        "MOCKINGBIRD_NODE_TRANSPORT_SPOOL_DIR",
        "MOCKINGBIRD_NODE_TRANSPORT_CREDENTIAL_STATE_PATH",
        "MOCKINGBIRD_NODE_TRANSPORT_CHUNK_SIZE_BYTES",
        "MOCKINGBIRD_NODE_TRANSPORT_MAX_CONCURRENT_UPLOADS",
        "MOCKINGBIRD_NODE_TRANSPORT_MAX_BYTES_PER_SECOND",
        "MOCKINGBIRD_NODE_TRANSPORT_BACKOFF_BASE_MS",
        "MOCKINGBIRD_NODE_TRANSPORT_BACKOFF_CAP_MS",
        "MOCKINGBIRD_NODE_TRANSPORT_SPOOL_MAX_BYTES",
        "MOCKINGBIRD_NODE_TRANSPORT_SPOOL_MAX_ITEMS",
        "MOCKINGBIRD_NODE_TRANSPORT_SPOOL_MIN_FREE_BYTES",
    ):
        monkeypatch.delenv(name, raising=False)


def test_unconfigured_host_address_means_transport_disabled(monkeypatch) -> None:
    _clear_transport_env(monkeypatch)
    config = CameraNodeConfig.from_environment()
    assert config.host_base_address is None
    assert config.transport_enabled is False
    # But a spool directory is still resolved -- durable retention does not
    # require a host to already be configured (see the design doc).
    assert config.transport_spool_dir is not None


def test_transport_paths_anchor_to_the_pairing_state_directory_not_home(monkeypatch, tmp_path) -> None:
    """Camera Node Upgrade & Compatibility Recovery v1: a real, reproduced
    defect found via genuine real-hardware upgrade acceptance. These two
    paths used to fall all the way through to `Path.home()` even when
    `MOCKINGBIRD_NODE_PAIRING_STATE_PATH` was explicitly set to something
    completely unrelated -- crashing every installer-managed Node (a
    dedicated system account with no real home directory, running under
    `ProtectHome=true`) the instant it upgraded past this codebase's own
    transport feature, regardless of whether transport was ever configured.
    Fixed by anchoring both to `pairing_state_path`'s own directory instead
    -- already guaranteed real/writable on every installer-managed device,
    the same way `pairing_state_path` itself already is."""

    _clear_transport_env(monkeypatch)
    state_dir = tmp_path / "var-lib-mockingbird-camera-node"
    monkeypatch.setenv("MOCKINGBIRD_NODE_PAIRING_STATE_PATH", str(state_dir / "pairing.json"))
    # A deliberately wrong/irrelevant HOME -- the result must not depend on
    # it at all once MOCKINGBIRD_NODE_PAIRING_STATE_PATH is set.
    monkeypatch.setenv("HOME", str(tmp_path / "not-a-real-home"))
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)

    config = CameraNodeConfig.from_environment()

    assert config.transport_spool_dir == state_dir / "transport"
    assert config.transport_credential_state_path == state_dir / "transport-credential.json"


def test_explicit_transport_spool_dir_still_overrides_the_pairing_anchored_default(monkeypatch, tmp_path) -> None:
    _clear_transport_env(monkeypatch)
    explicit = tmp_path / "custom-spool"
    monkeypatch.setenv("MOCKINGBIRD_NODE_TRANSPORT_SPOOL_DIR", str(explicit))
    config = CameraNodeConfig.from_environment()
    assert config.transport_spool_dir == explicit


def test_configured_host_address_enables_transport(monkeypatch) -> None:
    _clear_transport_env(monkeypatch)
    monkeypatch.setenv("MOCKINGBIRD_NODE_HOST_BASE_ADDRESS", "http://192.168.1.50:8000")
    config = CameraNodeConfig.from_environment()
    assert config.host_base_address == "http://192.168.1.50:8000"
    assert config.transport_enabled is True


def test_host_base_address_accepts_a_non_lan_hostname() -> None:
    # Deliberately the opposite of `normalize_camera_node_address` (host->
    # node, LAN-only): a remote Node's path back to the host may cross a
    # VPN/tunnel/public hostname.
    assert normalize_host_base_address("https://my-tunnel.example.com:9443") == "https://my-tunnel.example.com:9443"


@pytest.mark.parametrize("value", ["not-a-url", "ftp://host", "http://user:pass@host", "http://host/some/path", "http://host?query=1"])
def test_host_base_address_rejects_malformed_values(value) -> None:
    with pytest.raises(ValueError):
        normalize_host_base_address(value)


def test_transport_backoff_cap_must_not_be_below_base(monkeypatch) -> None:
    _clear_transport_env(monkeypatch)
    monkeypatch.setenv("MOCKINGBIRD_NODE_TRANSPORT_BACKOFF_BASE_MS", "5000")
    monkeypatch.setenv("MOCKINGBIRD_NODE_TRANSPORT_BACKOFF_CAP_MS", "1000")
    with pytest.raises(ValueError):
        CameraNodeConfig.from_environment()


def test_transport_numeric_bounds_are_enforced(monkeypatch) -> None:
    _clear_transport_env(monkeypatch)
    monkeypatch.setenv("MOCKINGBIRD_NODE_TRANSPORT_CHUNK_SIZE_BYTES", "10")  # below the 16384 minimum
    with pytest.raises(ValueError):
        CameraNodeConfig.from_environment()


def test_transport_defaults_are_conservative(monkeypatch) -> None:
    _clear_transport_env(monkeypatch)
    config = CameraNodeConfig.from_environment()
    assert config.transport_max_concurrent_uploads == 1
    assert config.transport_max_bytes_per_second == 0  # unpaced by default
    assert config.transport_spool_max_bytes > 0
    assert config.transport_spool_max_items > 0
    assert config.transport_backoff_cap_seconds >= config.transport_backoff_base_seconds


def test_direct_construction_with_no_transport_fields_degrades_gracefully() -> None:
    """Mirrors `pairing_state_path=None`'s existing degrade-gracefully
    contract: dozens of existing tests construct `CameraNodeConfig(...)`
    directly without knowing about these new fields."""

    config = CameraNodeConfig(
        display_name="test", bind_host="127.0.0.1", port=8787, provider_key="synthetic",
        camera_identifier=None, max_image_bytes=1_500_000, max_image_width=1920,
        max_image_height=1080, pairing_ttl_seconds=600, max_preview_viewers=2,
    )
    assert config.host_base_address is None
    assert config.transport_enabled is False
    assert config.transport_spool_dir is None
    assert config.transport_credential_state_path is None
