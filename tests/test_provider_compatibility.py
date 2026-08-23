"""Camera / Source + Multi-Camera Maturity v1, Phase D: the bounded
compatibility classification. Pure function calls only."""

from __future__ import annotations

from mockingbird.observation.provider_compatibility import (
    classify_provider_compatibility,
    provider_compatibility_label,
)


def test_camera_node_is_certified() -> None:
    assert classify_provider_compatibility("camera_node") == "certified"


def test_only_camera_node_is_certified() -> None:
    """Do NOT claim Certified merely because a provider exists."""

    others = (
        "external_url", "onvif", "local_usb", "manual_media", "folder_import_future",
        "webhook_future", "demo", "rtsp_future", "esp32_future", "browser_camera_future",
    )
    assert all(classify_provider_compatibility(key) != "certified" for key in others)


def test_import_only_providers_are_never_confused_with_unbuilt_stubs() -> None:
    """The exact gap this milestone's archaeology found: a fully-built,
    tested import path must not share a classification with genuine
    vaporware."""

    assert classify_provider_compatibility("manual_media") == "import_only"
    assert classify_provider_compatibility("folder_import_future") == "import_only"
    for stub in ("rtsp_future", "esp32_future", "browser_camera_future"):
        assert classify_provider_compatibility(stub) == "unsupported"
        assert classify_provider_compatibility(stub) != classify_provider_compatibility("folder_import_future")


def test_unknown_provider_key_is_honestly_unsupported() -> None:
    assert classify_provider_compatibility("some_future_key_nobody_registered") == "unsupported"
    assert classify_provider_compatibility(None) == "unsupported"


def test_every_level_has_a_plain_language_label() -> None:
    for level in ("certified", "compatible", "experimental", "import_only", "unsupported"):
        label = provider_compatibility_label(level)  # type: ignore[arg-type]
        assert label and label[0].isupper()
        assert "_" not in label
