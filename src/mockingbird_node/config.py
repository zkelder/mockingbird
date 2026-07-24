"""Validated, deliberately small local configuration for a Camera Node."""

from __future__ import annotations

from dataclasses import dataclass
import os


DEFAULT_PORT = 8787
DEFAULT_MAX_IMAGE_BYTES = 1_500_000
DEFAULT_MAX_IMAGE_WIDTH = 1920
DEFAULT_MAX_IMAGE_HEIGHT = 1080
DEFAULT_PAIRING_TTL_SECONDS = 10 * 60
DEFAULT_MAX_PREVIEW_VIEWERS = 2


@dataclass(frozen=True)
class CameraNodeConfig:
    display_name: str
    bind_host: str
    port: int
    provider_key: str
    camera_identifier: str | None
    max_image_bytes: int
    max_image_width: int
    max_image_height: int
    pairing_ttl_seconds: int
    max_preview_viewers: int
    testing: bool = False

    @classmethod
    def from_environment(cls) -> "CameraNodeConfig":
        def integer(name: str, default: int, *, minimum: int, maximum: int) -> int:
            raw = os.getenv(name, str(default)).strip()
            try:
                value = int(raw)
            except ValueError as error:
                raise ValueError(f"{name.lower()}_invalid") from error
            if not minimum <= value <= maximum:
                raise ValueError(f"{name.lower()}_invalid")
            return value

        display_name = os.getenv("MOCKINGBIRD_NODE_NAME", "MockingBird Camera Node").strip()
        if not display_name or len(display_name) > 120:
            raise ValueError("mockingbird_node_name_invalid")
        bind_host = os.getenv("MOCKINGBIRD_NODE_BIND", "127.0.0.1").strip()
        if bind_host not in {"127.0.0.1", "0.0.0.0", "::1", "::"}:
            raise ValueError("mockingbird_node_bind_invalid")
        provider_key = os.getenv("MOCKINGBIRD_NODE_PROVIDER", "v4l2").strip().lower()
        if provider_key not in {"v4l2", "picamera2", "synthetic"}:
            raise ValueError("mockingbird_node_provider_invalid")
        testing = os.getenv("MOCKINGBIRD_NODE_TESTING", "").strip().lower() in {"1", "true", "yes"}
        if provider_key == "synthetic" and not testing:
            raise ValueError("mockingbird_node_synthetic_testing_only")
        return cls(
            display_name=display_name,
            bind_host=bind_host,
            port=integer("MOCKINGBIRD_NODE_PORT", DEFAULT_PORT, minimum=1, maximum=65535),
            provider_key=provider_key,
            camera_identifier=os.getenv("MOCKINGBIRD_NODE_CAMERA", "").strip() or None,
            max_image_bytes=integer("MOCKINGBIRD_NODE_MAX_IMAGE_BYTES", DEFAULT_MAX_IMAGE_BYTES, minimum=32_768, maximum=8_000_000),
            max_image_width=integer("MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH", DEFAULT_MAX_IMAGE_WIDTH, minimum=160, maximum=3840),
            max_image_height=integer("MOCKINGBIRD_NODE_MAX_IMAGE_HEIGHT", DEFAULT_MAX_IMAGE_HEIGHT, minimum=120, maximum=2160),
            pairing_ttl_seconds=integer("MOCKINGBIRD_NODE_PAIRING_TTL_SECONDS", DEFAULT_PAIRING_TTL_SECONDS, minimum=60, maximum=3600),
            max_preview_viewers=integer("MOCKINGBIRD_NODE_MAX_PREVIEW_VIEWERS", DEFAULT_MAX_PREVIEW_VIEWERS, minimum=0, maximum=4),
            testing=testing,
        )
