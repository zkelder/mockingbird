"""Validated, deliberately small local configuration for a Camera Node."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


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
    enabled_providers: tuple[str, ...] = ()
    evidence_max_image_bytes: int | None = None
    evidence_max_image_width: int | None = None
    evidence_max_image_height: int | None = None
    pairing_state_path: Path | None = None

    @property
    def effective_evidence_max_image_bytes(self) -> int:
        return self.evidence_max_image_bytes or self.max_image_bytes

    @property
    def effective_evidence_max_image_width(self) -> int:
        return self.evidence_max_image_width or self.max_image_width

    @property
    def effective_evidence_max_image_height(self) -> int:
        return self.evidence_max_image_height or self.max_image_height

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
        requested = os.getenv(
            "MOCKINGBIRD_NODE_PROVIDERS",
            os.getenv("MOCKINGBIRD_NODE_PROVIDER", "auto"),
        ).strip().lower()
        enabled_providers = tuple(item.strip() for item in requested.split(",") if item.strip())
        if not enabled_providers or len(enabled_providers) > 2 or any(
            item not in {"auto", "v4l2", "picamera2", "synthetic"}
            for item in enabled_providers
        ):
            raise ValueError("mockingbird_node_provider_invalid")
        testing = os.getenv("MOCKINGBIRD_NODE_TESTING", "").strip().lower() in {"1", "true", "yes"}
        if "auto" in enabled_providers:
            if len(enabled_providers) != 1:
                raise ValueError("mockingbird_node_provider_invalid")
            enabled_providers = ("v4l2", "picamera2")
        if "synthetic" in enabled_providers and (not testing or len(enabled_providers) != 1):
            raise ValueError("mockingbird_node_synthetic_testing_only")
        max_image_bytes = integer(
            "MOCKINGBIRD_NODE_MAX_IMAGE_BYTES",
            DEFAULT_MAX_IMAGE_BYTES,
            minimum=32_768,
            maximum=32_000_000,
        )
        max_image_width = integer(
            "MOCKINGBIRD_NODE_MAX_IMAGE_WIDTH",
            DEFAULT_MAX_IMAGE_WIDTH,
            minimum=160,
            maximum=16_000,
        )
        max_image_height = integer(
            "MOCKINGBIRD_NODE_MAX_IMAGE_HEIGHT",
            DEFAULT_MAX_IMAGE_HEIGHT,
            minimum=120,
            maximum=12_000,
        )
        evidence_max_image_bytes = integer(
            "MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_BYTES",
            max_image_bytes,
            minimum=32_768,
            maximum=32_000_000,
        )
        evidence_max_image_width = integer(
            "MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_WIDTH",
            max_image_width,
            minimum=160,
            maximum=16_000,
        )
        evidence_max_image_height = integer(
            "MOCKINGBIRD_NODE_EVIDENCE_MAX_IMAGE_HEIGHT",
            max_image_height,
            minimum=120,
            maximum=12_000,
        )
        if (
            evidence_max_image_bytes < max_image_bytes
            or evidence_max_image_width < max_image_width
            or evidence_max_image_height < max_image_height
        ):
            raise ValueError("mockingbird_node_evidence_bounds_invalid")
        state_home = Path(
            os.getenv("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))
        )
        pairing_state_path = Path(
            os.getenv(
                "MOCKINGBIRD_NODE_PAIRING_STATE_PATH",
                str(state_home / "mockingbird-camera-node" / "pairing.json"),
            )
        ).expanduser()
        if not pairing_state_path.is_absolute():
            raise ValueError("mockingbird_node_pairing_state_path_invalid")
        return cls(
            display_name=display_name,
            bind_host=bind_host,
            port=integer("MOCKINGBIRD_NODE_PORT", DEFAULT_PORT, minimum=1, maximum=65535),
            provider_key=enabled_providers[0],
            camera_identifier=os.getenv("MOCKINGBIRD_NODE_CAMERA", "").strip() or None,
            max_image_bytes=max_image_bytes,
            max_image_width=max_image_width,
            max_image_height=max_image_height,
            pairing_ttl_seconds=integer("MOCKINGBIRD_NODE_PAIRING_TTL_SECONDS", DEFAULT_PAIRING_TTL_SECONDS, minimum=60, maximum=3600),
            max_preview_viewers=integer("MOCKINGBIRD_NODE_MAX_PREVIEW_VIEWERS", DEFAULT_MAX_PREVIEW_VIEWERS, minimum=0, maximum=4),
            testing=testing,
            enabled_providers=enabled_providers,
            # These opt-in bounds can exceed the economical monitoring profile
            # for one bounded evidence still. Omitting them preserves the
            # established snapshot-only Node behavior.
            evidence_max_image_bytes=evidence_max_image_bytes,
            evidence_max_image_width=evidence_max_image_width,
            evidence_max_image_height=evidence_max_image_height,
            pairing_state_path=pairing_state_path,
        )
