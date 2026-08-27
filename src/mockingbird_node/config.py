"""Validated, deliberately small local configuration for a Camera Node."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


DEFAULT_PORT = 8787
DEFAULT_MAX_IMAGE_BYTES = 1_500_000
DEFAULT_MAX_IMAGE_WIDTH = 1920
DEFAULT_MAX_IMAGE_HEIGHT = 1080
DEFAULT_PAIRING_TTL_SECONDS = 10 * 60
DEFAULT_MAX_PREVIEW_VIEWERS = 2
DEFAULT_LOG_LEVEL = "warning"

# Remote / Intermittent-WAN Transport Foundation v1: the Node's own outbound
# delivery defaults. Deliberately conservative for Pi-class hardware and an
# unknown/possibly-metered link -- see docs/remote-intermittent-wan
# -transport-v1-design.md "Bandwidth-aware policy" and "Bounds / eviction".
DEFAULT_TRANSPORT_CHUNK_SIZE_BYTES = 262_144
DEFAULT_TRANSPORT_MAX_CONCURRENT_UPLOADS = 1
DEFAULT_TRANSPORT_MAX_BYTES_PER_SECOND = 0  # 0 == unpaced
DEFAULT_TRANSPORT_BACKOFF_BASE_SECONDS = 2.0
DEFAULT_TRANSPORT_BACKOFF_CAP_SECONDS = 300.0
DEFAULT_TRANSPORT_SPOOL_MAX_BYTES = 512_000_000
DEFAULT_TRANSPORT_SPOOL_MAX_ITEMS = 2000
DEFAULT_TRANSPORT_SPOOL_MIN_FREE_BYTES = 100_000_000
# uvicorn's own accepted `log_level` values (uvicorn.config.LOG_LEVELS keys).
# Validated here rather than left to uvicorn's own error path so a bad value
# fails through the same clean `CameraNodeConfig` error surface as every
# other field -- see "Diagnostics implementation" in
# docs/camera-node-installer-design.md.
_VALID_LOG_LEVELS = frozenset({"critical", "error", "warning", "info", "debug", "trace"})


def normalize_host_base_address(value: str) -> str:
    """Validate a Node->host address without the host->node LAN restriction.

    A remote Camera Node's path back to the host may legitimately cross a
    VPN/tunnel/dyndns hostname -- provisioning that path is explicitly out
    of this milestone's scope (see "Scope exclusions": no VPN/mobile
    remote-access product, no cloud relay). This only rejects an
    obviously-malformed address (embedded credentials, a query/fragment, a
    sub-path, an unsupported scheme) the same way
    `camera_node.normalize_camera_node_address` already does for the
    opposite direction, so a bad value fails fast and safely rather than
    surfacing as a mysterious connection failure later.
    """

    raw = value.strip()
    if not raw or len(raw) > 260:
        raise ValueError("mockingbird_node_host_base_address_invalid")
    parsed = urlsplit(raw)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
    ):
        raise ValueError("mockingbird_node_host_base_address_invalid")
    host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    return urlunsplit((parsed.scheme.lower(), host if parsed.port is None else f"{host}:{parsed.port}", "", "", ""))


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
    log_level: str = DEFAULT_LOG_LEVEL
    testing: bool = False
    enabled_providers: tuple[str, ...] = ()
    evidence_max_image_bytes: int | None = None
    evidence_max_image_width: int | None = None
    evidence_max_image_height: int | None = None
    pairing_state_path: Path | None = None
    # Remote / Intermittent-WAN Transport Foundation v1. `host_base_address`
    # is None by default: an un-configured Node keeps behaving exactly as
    # before (no outbound worker starts -- see `transport_enabled`). Unlike
    # `normalize_camera_node_address` (host->node, LAN-only by design), this
    # address is Node->host and, for a genuinely remote node, may legitimately
    # be a VPN/tunnel/public hostname -- so it is validated but not
    # LAN-restricted; see `normalize_host_base_address`.
    host_base_address: str | None = None
    transport_spool_dir: Path | None = None
    transport_credential_state_path: Path | None = None
    transport_chunk_size_bytes: int = DEFAULT_TRANSPORT_CHUNK_SIZE_BYTES
    transport_max_concurrent_uploads: int = DEFAULT_TRANSPORT_MAX_CONCURRENT_UPLOADS
    transport_max_bytes_per_second: int = DEFAULT_TRANSPORT_MAX_BYTES_PER_SECOND
    transport_backoff_base_seconds: float = DEFAULT_TRANSPORT_BACKOFF_BASE_SECONDS
    transport_backoff_cap_seconds: float = DEFAULT_TRANSPORT_BACKOFF_CAP_SECONDS
    transport_spool_max_bytes: int = DEFAULT_TRANSPORT_SPOOL_MAX_BYTES
    transport_spool_max_items: int = DEFAULT_TRANSPORT_SPOOL_MAX_ITEMS
    transport_spool_min_free_bytes: int = DEFAULT_TRANSPORT_SPOOL_MIN_FREE_BYTES

    @property
    def effective_evidence_max_image_bytes(self) -> int:
        return self.evidence_max_image_bytes or self.max_image_bytes

    @property
    def effective_evidence_max_image_width(self) -> int:
        return self.evidence_max_image_width or self.max_image_width

    @property
    def effective_evidence_max_image_height(self) -> int:
        return self.evidence_max_image_height or self.max_image_height

    @property
    def transport_enabled(self) -> bool:
        """No host configured yet == transport worker never starts.

        Never a crash, never a required field: the product must keep
        working exactly as it does today for an operator who has not
        opted into remote delivery -- see the milestone's "no assumption of
        constant host reachability" doctrine, which cuts both ways (a Node
        with no host address configured is not an error state).
        """

        return bool(self.host_base_address)

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
        log_level = os.getenv("MOCKINGBIRD_NODE_LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().lower()
        if log_level not in _VALID_LOG_LEVELS:
            raise ValueError("mockingbird_node_log_level_invalid")

        raw_host_base_address = os.getenv("MOCKINGBIRD_NODE_HOST_BASE_ADDRESS", "").strip()
        host_base_address = normalize_host_base_address(raw_host_base_address) if raw_host_base_address else None
        # Camera Node Upgrade & Compatibility Recovery v1: a real, reproduced
        # defect found via genuine real-hardware upgrade acceptance. These two
        # paths previously defaulted to `state_home` (itself falling back to
        # `Path.home()`) -- the *same* fallback `pairing_state_path`, above,
        # uses, but `pairing_state_path` is never actually affected by it on
        # any installer-managed device, because `scripts/install_camera_
        # node.py` always writes `MOCKINGBIRD_NODE_PAIRING_STATE_PATH`
        # explicitly into `node.env` (an intentional, documented choice --
        # see "State paths" in docs/camera-node-installer-design.md: "an
        # explicit, predictable, documented path rather than an inherited
        # guess"). Nothing gave the transport paths that same treatment, so
        # they silently fell all the way through to `Path.home()` on a
        # dedicated system account with no real home directory
        # (`useradd --no-create-home`) running under `ProtectSystem=strict`/
        # `ProtectHome=true` -- `TransportSpool`'s own `mkdir` then raised an
        # uncaught `PermissionError`, crashing *every* Node at startup the
        # instant it upgraded past Remote / Intermittent-WAN Transport
        # Foundation v1, regardless of whether the operator ever opted into
        # transport. Confirmed by direct reproduction on the project's real
        # reference Pi -- see "Real acceptance" in
        # docs/camera-node-upgrade-compatibility-recovery-v1-report.md.
        # Fixed by giving the transport paths the identical treatment
        # pairing state already has: anchored to `pairing_state_path`'s own
        # directory (always a real, writable, already-correctly-configured
        # location on every installer-managed device -- `StateDirectory=`'s
        # own grant survives `ProtectSystem=strict`) rather than a second,
        # independent, unreliable `state_home` guess. This preserves the
        # original design intent unchanged (a spool directory is still
        # always resolved regardless of whether a host is configured yet --
        # durable retention does not require transport to already be
        # enabled) while fixing only the broken default *location*; an
        # explicit environment override still always wins.
        transport_spool_dir = Path(
            os.getenv("MOCKINGBIRD_NODE_TRANSPORT_SPOOL_DIR", str(pairing_state_path.parent / "transport"))
        ).expanduser()
        if not transport_spool_dir.is_absolute():
            raise ValueError("mockingbird_node_transport_spool_dir_invalid")
        transport_credential_state_path = Path(
            os.getenv(
                "MOCKINGBIRD_NODE_TRANSPORT_CREDENTIAL_STATE_PATH",
                str(pairing_state_path.parent / "transport-credential.json"),
            )
        ).expanduser()
        if not transport_credential_state_path.is_absolute():
            raise ValueError("mockingbird_node_transport_credential_state_path_invalid")
        transport_backoff_base_seconds = float(
            integer(
                "MOCKINGBIRD_NODE_TRANSPORT_BACKOFF_BASE_MS",
                int(DEFAULT_TRANSPORT_BACKOFF_BASE_SECONDS * 1000),
                minimum=100,
                maximum=60_000,
            )
        ) / 1000.0
        transport_backoff_cap_seconds = float(
            integer(
                "MOCKINGBIRD_NODE_TRANSPORT_BACKOFF_CAP_MS",
                int(DEFAULT_TRANSPORT_BACKOFF_CAP_SECONDS * 1000),
                minimum=1_000,
                maximum=3_600_000,
            )
        ) / 1000.0
        if transport_backoff_cap_seconds < transport_backoff_base_seconds:
            raise ValueError("mockingbird_node_transport_backoff_invalid")
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
            log_level=log_level,
            testing=testing,
            enabled_providers=enabled_providers,
            # These opt-in bounds can exceed the economical monitoring profile
            # for one bounded evidence still. Omitting them preserves the
            # established snapshot-only Node behavior.
            evidence_max_image_bytes=evidence_max_image_bytes,
            evidence_max_image_width=evidence_max_image_width,
            evidence_max_image_height=evidence_max_image_height,
            pairing_state_path=pairing_state_path,
            host_base_address=host_base_address,
            transport_spool_dir=transport_spool_dir,
            transport_credential_state_path=transport_credential_state_path,
            transport_chunk_size_bytes=integer(
                "MOCKINGBIRD_NODE_TRANSPORT_CHUNK_SIZE_BYTES",
                DEFAULT_TRANSPORT_CHUNK_SIZE_BYTES,
                minimum=16_384,
                maximum=4_000_000,
            ),
            transport_max_concurrent_uploads=integer(
                "MOCKINGBIRD_NODE_TRANSPORT_MAX_CONCURRENT_UPLOADS",
                DEFAULT_TRANSPORT_MAX_CONCURRENT_UPLOADS,
                minimum=1,
                maximum=4,
            ),
            transport_max_bytes_per_second=integer(
                "MOCKINGBIRD_NODE_TRANSPORT_MAX_BYTES_PER_SECOND",
                DEFAULT_TRANSPORT_MAX_BYTES_PER_SECOND,
                minimum=0,
                maximum=1_000_000_000,
            ),
            transport_backoff_base_seconds=transport_backoff_base_seconds,
            transport_backoff_cap_seconds=transport_backoff_cap_seconds,
            transport_spool_max_bytes=integer(
                "MOCKINGBIRD_NODE_TRANSPORT_SPOOL_MAX_BYTES",
                DEFAULT_TRANSPORT_SPOOL_MAX_BYTES,
                minimum=1_000_000,
                maximum=10_000_000_000,
            ),
            transport_spool_max_items=integer(
                "MOCKINGBIRD_NODE_TRANSPORT_SPOOL_MAX_ITEMS",
                DEFAULT_TRANSPORT_SPOOL_MAX_ITEMS,
                minimum=1,
                maximum=100_000,
            ),
            transport_spool_min_free_bytes=integer(
                "MOCKINGBIRD_NODE_TRANSPORT_SPOOL_MIN_FREE_BYTES",
                DEFAULT_TRANSPORT_SPOOL_MIN_FREE_BYTES,
                minimum=0,
                maximum=10_000_000_000,
            ),
        )
