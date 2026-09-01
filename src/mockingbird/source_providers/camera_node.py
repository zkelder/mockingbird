"""Strict main-app client for one explicitly configured Camera Node address.

The client never discovers hosts, follows redirects, uses caller-provided paths,
or logs bearer credentials. Pairing is explicit; ordinary status reads do not
instantiate this client or contact a Node.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import HTTPConnection, HTTPSConnection
import ipaddress
import json
import secrets
import socket
import time
from typing import Any, Callable, Protocol
from urllib.parse import urlsplit, urlunsplit


NODE_API_VERSION = "v1"
MAX_NODE_JSON_BYTES = 128_000
MAX_NODE_SNAPSHOT_BYTES = 1_500_000
MAX_NODE_CAPTURE_BYTES = 16_000_000
NODE_CONNECT_TIMEOUT_SECONDS = 2.0
NODE_METADATA_RESPONSE_TIMEOUT_SECONDS = 3.0
NODE_WARM_SNAPSHOT_RESPONSE_TIMEOUT_SECONDS = 4.0
NODE_COLD_SNAPSHOT_RESPONSE_TIMEOUT_SECONDS = 8.0
NODE_MAX_SNAPSHOT_RESPONSE_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class CameraNodeRequestTiming:
    """Fixed, bounded transport timing; Nodes cannot extend the global limit."""

    connect_timeout_seconds: float
    response_timeout_seconds: float
    maximum_seconds: float
    timeout_error: str


NODE_METADATA_TIMING = CameraNodeRequestTiming(
    connect_timeout_seconds=NODE_CONNECT_TIMEOUT_SECONDS,
    response_timeout_seconds=NODE_METADATA_RESPONSE_TIMEOUT_SECONDS,
    maximum_seconds=NODE_METADATA_RESPONSE_TIMEOUT_SECONDS,
    timeout_error="node_unavailable",
)


CAMERA_NODE_RUNTIME_FAILURE_CODES = frozenset(
    {
        "authentication_rejected",
        "node_camera_warmup_timeout",
        "node_camera_unavailable",
        "node_snapshot_invalid",
        "node_snapshot_timeout",
        "node_capture_profile_unavailable",
        "node_unavailable",
        "provider_reset_required",
        "provider_session_failed",
        "provider_warming",
    }
)

_NODE_SNAPSHOT_ERROR_HEADER = "X-MockingBird-Node-Error"
_NODE_MONITORING_RECOVERY_HEADER = "X-MockingBird-Monitoring-Recovery"
_NODE_MONITORING_RECOVERY_STATES = frozenset({"restored", "reset_required"})
_NODE_SNAPSHOT_ERROR_CODES = frozenset(
    {
        "node_camera_unavailable",
        "node_camera_warmup_timeout",
        "node_snapshot_invalid",
        "node_snapshot_timeout",
        "node_capture_profile_unavailable",
        "provider_reset_required",
        "profile_not_advertised",
        "provider_session_failed",
    }
)
_NODE_SNAPSHOT_ERROR_ALIASES = {
    "profile_not_advertised": "node_capture_profile_unavailable",
}



class CameraNodeClientError(ValueError):
    """Safe client error codes only; raw host/credential/transport text is discarded."""

    def __init__(self, code: str, *, failure_class: str | None = None) -> None:
        super().__init__(code)
        # Camera Node Connectivity & Recovery Diagnosis v1: an optional,
        # bounded, safe (a fixed vocabulary word, never raw host/port/
        # message text) sub-classification of *why* a transport-level code
        # such as `analysis_stream_unavailable` occurred -- connection
        # refused, timed out, reset, or a bad HTTP response, for example.
        # Purely additive diagnostic detail: `code` (this exception's own
        # `str()`) remains the single source of truth every existing
        # retry/terminal-classification check already matches against;
        # `failure_class` is never used for control flow, only surfaced
        # into advanced diagnostics so an operator (or a future automated
        # check) can tell these apart without Camera Node-side log access.
        self.failure_class = failure_class


@dataclass(frozen=True)
class CameraNodeCamera:
    camera_id: str
    display_name: str
    status: str
    snapshot_supported: bool
    setup_hint: str | None = None
    provider_type: str | None = None
    capture_profiles: tuple["CameraNodeCaptureProfile", ...] = ()
    capture_readiness: str = "not_initialized"
    capture_profile_status: tuple["CameraNodeCaptureProfileStatus", ...] = ()


@dataclass(frozen=True)
class CameraNodeCaptureProfile:
    """An opaque Node-controlled image profile, never a driver configuration."""

    profile_id: str
    purposes: tuple[str, ...]
    width: int
    height: int
    jpeg_supported: bool
    max_expected_bytes: int
    capture_class: str
    geometry_group: str | None
    orientation: str
    mirrored: bool
    same_fov: bool

    @property
    def supports_monitoring(self) -> bool:
        return "monitoring" in self.purposes

    @property
    def supports_evidence(self) -> bool:
        return "evidence" in self.purposes


@dataclass(frozen=True)
class CameraNodeCaptureProfileStatus:
    """Safe optional warm-proof state from a profile-aware Camera Node."""

    profile_id: str
    state: str


@dataclass(frozen=True)
class CameraNodeCapture:
    image: bytes
    profile_id: str
    captured_at: datetime | None
    width: int
    height: int
    monitoring_recovery: str | None = None


@dataclass(frozen=True)
class CameraNodePairing:
    base_address: str
    node_id: str
    display_name: str
    api_version: str
    credential: str
    cameras: list[CameraNodeCamera]
    capability_fingerprint: str
    recommended_snapshot_timeout_seconds: float | None = None
    # Remote / Intermittent-WAN Transport Foundation v1: additive-only --
    # absent (None) from an old Node that predates transport, or one with
    # no host address configured (see `CameraNodeConfig.transport_enabled`
    # on the Node side). A *separate* secret from `credential` above; see
    # `mockingbird_node.transport_credential`'s module docstring for why.
    transport_credential: str | None = None


class CameraNodeRequester(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        max_bytes: int,
        timing: CameraNodeRequestTiming,
    ) -> tuple[int, dict[str, str], bytes]: ...


class UrlLibCameraNodeRequester:
    """Fixed-path local client with separate connect and bounded response windows."""

    @staticmethod
    def _connection(url: str, *, connect_timeout_seconds: float) -> tuple[HTTPConnection | HTTPSConnection, str]:
        parsed = urlsplit(url)
        path = parsed.path or "/"
        if parsed.scheme == "http":
            return HTTPConnection(parsed.netloc, timeout=connect_timeout_seconds), path
        if parsed.scheme == "https":
            return HTTPSConnection(parsed.netloc, timeout=connect_timeout_seconds), path
        raise CameraNodeClientError("node_endpoint_invalid")

    @staticmethod
    def _read_response(
        connection: HTTPConnection | HTTPSConnection,
        response: Any,
        *,
        max_bytes: int,
        timing: CameraNodeRequestTiming,
    ) -> bytes:
        deadline = time.monotonic() + timing.maximum_seconds
        data = bytearray()
        while len(data) <= max_bytes:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError
            if connection.sock is not None:
                connection.sock.settimeout(min(timing.response_timeout_seconds, remaining))
            chunk = response.read(min(64 * 1024, max_bytes + 1 - len(data)))
            if not chunk:
                return bytes(data)
            data.extend(chunk)
        return bytes(data)

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
        max_bytes: int,
        timing: CameraNodeRequestTiming,
    ) -> tuple[int, dict[str, str], bytes]:
        connection: HTTPConnection | HTTPSConnection | None = None
        try:
            connection, path = self._connection(url, connect_timeout_seconds=timing.connect_timeout_seconds)
            try:
                connection.request(method, path, body=body, headers=headers)
            except (socket.timeout, TimeoutError, OSError) as error:
                raise CameraNodeClientError("node_unavailable") from error
            try:
                if connection.sock is not None:
                    connection.sock.settimeout(min(timing.response_timeout_seconds, timing.maximum_seconds))
                response = connection.getresponse()
                data = self._read_response(connection, response, max_bytes=max_bytes, timing=timing)
            except (socket.timeout, TimeoutError) as error:
                raise CameraNodeClientError(timing.timeout_error) from error
            except OSError as error:
                raise CameraNodeClientError("node_unavailable") from error
            return response.status, dict(response.headers.items()), data
        finally:
            if connection is not None:
                connection.close()


def _snapshot_timing(recommended_timeout_seconds: float | None = None) -> CameraNodeRequestTiming:
    response_timeout_seconds = NODE_COLD_SNAPSHOT_RESPONSE_TIMEOUT_SECONDS
    if isinstance(recommended_timeout_seconds, (int, float)) and not isinstance(recommended_timeout_seconds, bool):
        response_timeout_seconds = min(
            max(float(recommended_timeout_seconds), NODE_WARM_SNAPSHOT_RESPONSE_TIMEOUT_SECONDS),
            NODE_MAX_SNAPSHOT_RESPONSE_TIMEOUT_SECONDS,
        )
    return CameraNodeRequestTiming(
        connect_timeout_seconds=NODE_CONNECT_TIMEOUT_SECONDS,
        response_timeout_seconds=response_timeout_seconds,
        maximum_seconds=NODE_MAX_SNAPSHOT_RESPONSE_TIMEOUT_SECONDS,
        timeout_error="node_snapshot_timeout",
    )


def _recommended_snapshot_timeout(value: object) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return _snapshot_timing(float(value)).response_timeout_seconds


def _transport_credential(value: object) -> str | None:
    # C3 additive compatibility (same reasoning as `_camera_items` elsewhere
    # in this module): an old Node, or one with no host address configured,
    # simply omits this field. Anything present but malformed is treated the
    # same as absent (never a hard pairing failure over optional transport
    # metadata) -- see Remote / Intermittent-WAN Transport Foundation v1.
    if not isinstance(value, str) or not value or len(value) > 160:
        return None
    return value


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            return None
        length = int.from_bytes(data[index:index + 2], "big")
        if length < 2 or index + length > len(data):
            return None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            return (
                int.from_bytes(data[index + 5:index + 7], "big"),
                int.from_bytes(data[index + 3:index + 5], "big"),
            )
        index += length
    return None


def _captured_at_header(headers: dict[str, str]) -> datetime | None:
    value = headers.get("X-MockingBird-Captured-At", headers.get("x-mockingbird-captured-at"))
    if not value or len(value) > 80:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def normalize_camera_node_address(value: str) -> str:
    """Accept an explicit LAN IP base URL only; endpoint paths never come from UI."""
    raw = value.strip()
    if not raw or len(raw) > 260:
        raise CameraNodeClientError("node_address_invalid")
    parsed = urlsplit(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in {"", "/"}:
        raise CameraNodeClientError("node_address_invalid")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError as error:
        raise CameraNodeClientError("node_address_requires_lan_ip") from error
    if not (address.is_private or address.is_loopback or address.is_link_local):
        raise CameraNodeClientError("node_address_not_local")
    host = f"[{parsed.hostname}]" if address.version == 6 else parsed.hostname
    return urlunsplit((parsed.scheme.lower(), host if parsed.port is None else f"{host}:{parsed.port}", "", "", ""))


def _node_url(base_address: str, path: str) -> str:
    if not path.startswith("/node/v1/") or "?" in path or "#" in path:
        raise CameraNodeClientError("node_endpoint_invalid")
    return f"{base_address}{path}"


def _safe_json(data: bytes) -> dict[str, Any]:
    if len(data) > MAX_NODE_JSON_BYTES:
        raise CameraNodeClientError("node_response_too_large")
    try:
        decoded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CameraNodeClientError("node_response_invalid") from error
    if not isinstance(decoded, dict):
        raise CameraNodeClientError("node_response_invalid")
    return decoded


def _camera_items(value: object) -> list[CameraNodeCamera]:
    if not isinstance(value, list) or len(value) > 16:
        raise CameraNodeClientError("node_response_invalid")
    cameras: list[CameraNodeCamera] = []
    for item in value:
        if not isinstance(item, dict):
            raise CameraNodeClientError("node_response_invalid")
        camera_id, display_name, status = item.get("camera_id"), item.get("display_name"), item.get("status")
        if not all(isinstance(candidate, str) and candidate for candidate in (camera_id, display_name, status)) or len(camera_id) > 120 or len(display_name) > 120:
            raise CameraNodeClientError("node_response_invalid")
        # First-Hour Onboarding + Whole-Product Observability Closure v1
        # ("C3 additive compatibility"): a genuinely new status value from a
        # newer Node used to hard-crash the whole camera list. `status` is
        # purely presentational -- unlike `capture_class` below, nothing
        # downstream branches on it to make a real capture decision -- so an
        # unrecognized value soft-falls to the existing, already-handled
        # `unavailable` state (the conservative "can't confirm this camera
        # is usable" reading) rather than refusing the entire response.
        if status not in {"available", "setup_required", "unavailable"}:
            status = "unavailable"
        hint, provider_type = item.get("setup_hint"), item.get("provider_type")
        readiness = item.get("capture_readiness", "not_initialized")
        cameras.append(
            CameraNodeCamera(
                camera_id,
                display_name,
                status,
                bool(item.get("snapshot_supported")),
                hint if isinstance(hint, str) and len(hint) <= 240 else None,
                provider_type if provider_type in {"v4l2", "picamera2", "synthetic", "local"} else None,
                tuple(_capture_profiles(item.get("capture_profiles"))),
                readiness
                if isinstance(readiness, str)
                and readiness
                in {"not_initialized", "warming", "ready", "degraded", "unavailable"}
                else "unavailable",
                tuple(_capture_profile_status(item.get("capture_profile_status"))),
            )
        )
    return cameras


def _capture_profile_status(value: object) -> list[CameraNodeCaptureProfileStatus]:
    """Read the fixed, sanitized warm-proof vocabulary without raw diagnostics."""

    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 12:
        raise CameraNodeClientError("node_response_invalid")
    allowed_states = {
        "untested",
        "testing",
        "accepted",
        "rejected_resource",
        "rejected_alignment",
        "rejected_latency",
        "rejected_capture",
        "rejected_configuration",
    }
    statuses: list[CameraNodeCaptureProfileStatus] = []
    for item in value:
        if not isinstance(item, dict):
            raise CameraNodeClientError("node_response_invalid")
        profile_id, state = item.get("profile_id"), item.get("state")
        if (
            not isinstance(profile_id, str)
            or not profile_id
            or len(profile_id) > 120
            or "/" in profile_id
            or not isinstance(state, str)
        ):
            raise CameraNodeClientError("node_response_invalid")
        # C3 additive compatibility (see `_camera_items`): this is bounded,
        # sanitized diagnostic-only text ("Read the fixed, sanitized
        # warm-proof vocabulary without raw diagnostics" -- see this
        # function's own docstring), never a value anything branches real
        # capture behavior on. An unrecognized state from a newer Node
        # soft-falls to "untested" (an honest "not evaluated yet" reading)
        # instead of discarding the whole profile-status list.
        if state not in allowed_states:
            state = "untested"
        statuses.append(CameraNodeCaptureProfileStatus(profile_id, state))
    if len({status.profile_id for status in statuses}) != len(statuses):
        raise CameraNodeClientError("node_response_invalid")
    return statuses


def _capture_profiles(value: object) -> list[CameraNodeCaptureProfile]:
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > 12:
        raise CameraNodeClientError("node_response_invalid")
    profiles: list[CameraNodeCaptureProfile] = []
    allowed_purposes = {"monitoring", "preview", "evidence"}
    for item in value:
        if not isinstance(item, dict):
            raise CameraNodeClientError("node_response_invalid")
        profile_id = item.get("profile_id")
        purposes = item.get("purposes")
        width, height = item.get("width"), item.get("height")
        max_expected_bytes = item.get("max_expected_bytes")
        capture_class = item.get("capture_class")
        geometry_group = item.get("geometry_group")
        orientation = item.get("orientation", "normal")
        if (
            not isinstance(profile_id, str)
            or not profile_id
            or len(profile_id) > 120
            or "/" in profile_id
            or not isinstance(purposes, list)
            or not purposes
            or len(purposes) > 3
            or any(not isinstance(value, str) or value not in allowed_purposes for value in purposes)
            or len(set(purposes)) != len(purposes)
            or not isinstance(width, int)
            or not isinstance(height, int)
            or not 1 <= width <= 16_000
            or not 1 <= height <= 12_000
            or not isinstance(max_expected_bytes, int)
            or not 32_768 <= max_expected_bytes <= MAX_NODE_CAPTURE_BYTES
            # `capture_class` deliberately stays a hard requirement, unlike
            # `status`/`state`/`orientation` elsewhere in this module (C3
            # additive compatibility): downstream capture-decision code
            # branches on its exact literal value to choose real capture
            # behavior (warm vs. reconfiguration), which this milestone did
            # not trace end-to-end -- an unrecognized value here honestly
            # refuses the response rather than silently guessing a
            # capture-behavior fallback that could be wrong in a way a
            # simple presentational default cannot be. See the First-Hour
            # Onboarding + Whole-Product Observability Closure v1 report's
            # "known limitations" for why this one field was left as-is.
            or capture_class not in {
                "warm",
                "reconfiguration",
                "warm_concurrent",
                "reconfiguration_required",
            }
            or (geometry_group is not None and (not isinstance(geometry_group, str) or len(geometry_group) > 120))
        ):
            raise CameraNodeClientError("node_response_invalid")
        # C3 additive compatibility (see `_camera_items`): orientation is
        # already defaulted to "normal" when the *key itself* is absent
        # (the `.get("orientation", "normal")` above); an unrecognized-but-
        # present value now gets the identical, already-used fallback
        # instead of discarding the whole profile.
        if orientation not in {"normal", "rotate_90", "rotate_180", "rotate_270"}:
            orientation = "normal"
        profiles.append(
            CameraNodeCaptureProfile(
                profile_id=profile_id,
                purposes=tuple(purposes),
                width=width,
                height=height,
                jpeg_supported=bool(item.get("jpeg_supported")),
                max_expected_bytes=max_expected_bytes,
                capture_class=capture_class,
                geometry_group=geometry_group,
                orientation=orientation,
                mirrored=bool(item.get("mirrored")),
                same_fov=bool(item.get("same_fov")),
            )
        )
    if len({profile.profile_id for profile in profiles}) != len(profiles):
        raise CameraNodeClientError("node_response_invalid")
    return profiles


@dataclass(frozen=True)
class CameraNodeRoundTripSample:
    """One bracketed request/response measurement against the existing
    `/node/v1/health` operation, reused (not a new time-sync protocol) for
    Camera Node <-> Host RTT-Bounded Clock Calibration v1 -- see
    docs/camera-node-host-rtt-bounded-clock-calibration-v1-report.md
    "Existing protocol investigation". Plain data only; the actual
    interval-bound estimation lives in `observation.clock_calibration`
    (this module never imports that package, preserving the existing
    `observation` -> `source_providers` dependency direction rather than
    reversing it -- a caller that has both converts this into a
    `clock_calibration.RttRoundTrip`).

    `node_receive_time`/`node_response_time` are `None` whenever an old
    Node's `/node/v1/health` response predates this milestone (no such
    keys at all) or the value fails to parse as a genuine tz-aware
    timestamp -- never a crash, matching this client's own established
    "safe error codes only" discipline."""

    host_send_at: datetime
    host_receive_at: datetime
    node_receive_time: datetime | None
    node_response_time: datetime | None


def _parse_node_timestamp(value: object) -> datetime | None:
    """`None` (never a guess, never a raised error) for anything that is
    not a well-formed, tz-aware ISO timestamp -- an old Node lacking the
    key, a malformed value, or a naive one are all treated identically:
    this specific round-trip sample simply cannot be used for calibration
    (see `clock_calibration.py`'s own "Old Node compatibility")."""

    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


class CameraNodeClient:
    def __init__(self, *, requester: CameraNodeRequester | None = None) -> None:
        self._requester = requester or UrlLibCameraNodeRequester()

    def _request(
        self,
        *,
        base_address: str,
        path: str,
        method: str = "GET",
        credential: str | None = None,
        payload: dict[str, str] | None = None,
        max_bytes: int = MAX_NODE_JSON_BYTES,
        timing: CameraNodeRequestTiming = NODE_METADATA_TIMING,
    ) -> tuple[int, dict[str, str], bytes]:
        headers = {"Accept": "application/json", "Cache-Control": "no-store"}
        body = None
        if credential:
            headers["Authorization"] = f"Bearer {credential}"
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        status, response_headers, data = self._requester.request(
            method=method,
            url=_node_url(base_address, path),
            headers=headers,
            body=body,
            max_bytes=max_bytes,
            timing=timing,
        )
        if len(data) > max_bytes:
            raise CameraNodeClientError("node_response_too_large")
        if 300 <= status < 400:
            raise CameraNodeClientError("node_redirect_rejected")
        return status, response_headers, data

    def health(self, base_address: str) -> dict[str, Any]:
        base = normalize_camera_node_address(base_address)
        status, _, data = self._request(base_address=base, path="/node/v1/health")
        if status != 200:
            raise CameraNodeClientError("node_unavailable")
        return _safe_json(data)

    def sample_clock_round_trip(
        self, base_address: str, *, clock: Callable[[], datetime] | None = None,
    ) -> CameraNodeRoundTripSample:
        """Camera Node <-> Host RTT-Bounded Clock Calibration v1: one
        bracketed `H0 -> GET /node/v1/health -> H1` measurement, reusing
        this existing metadata request rather than a dedicated time-sync
        call (see docs/camera-node-host-rtt-bounded-clock-calibration-v1
        -report.md). `clock` defaults to the same canonical `datetime.
        now(UTC)` read every other Host-side timestamp in this codebase
        uses; a caller (an `_EngineSession`'s own injected clock) should
        pass its own for deterministic tests, matching the established
        `clock=` convention (`engine_runtime._EngineSession.__init__`).

        No pairing credential is sent or required -- `/node/v1/health`
        itself needs none (see `mockingbird_node.app.health`); this
        mirrors `health()` above exactly. Raises `CameraNodeClientError`
        on any transport failure (a non-200 status, a timeout, a
        connection error) -- the caller is expected to treat one failed
        probe as simply "this sample never happened," never fatal to a
        live session (see `engine_runtime._EngineSession`'s own RTT
        calibration batch, which tolerates individual probe failures)."""

        read_clock = clock or (lambda: datetime.now(UTC))
        base = normalize_camera_node_address(base_address)
        host_send_at = read_clock()
        status, _, data = self._request(base_address=base, path="/node/v1/health")
        host_receive_at = read_clock()
        if status != 200:
            raise CameraNodeClientError("node_unavailable")
        body = _safe_json(data)
        return CameraNodeRoundTripSample(
            host_send_at=host_send_at,
            host_receive_at=host_receive_at,
            node_receive_time=_parse_node_timestamp(body.get("node_receive_time")),
            node_response_time=_parse_node_timestamp(body.get("node_time")),
        )

    def pair(self, base_address: str, pairing_code: str) -> CameraNodePairing:
        base = normalize_camera_node_address(base_address)
        code = pairing_code.strip()
        if not code or len(code) > 128:
            # Never sent to the Node at all -- a malformed request, not a
            # verdict from the Node about the code's correctness.
            raise CameraNodeClientError("pairing_code_malformed")
        status, _, data = self._request(base_address=base, path="/node/v1/pair", method="POST", payload={"pairing_code": code})
        if status == 410:
            raise CameraNodeClientError("pairing_code_expired")
        if status == 429:
            raise CameraNodeClientError("pairing_rate_limited")
        if status == 409:
            # The Node's one-time code is single-use; 409 means *some* pair()
            # call already consumed it -- a local repair-state question ("did
            # my last attempt actually succeed?"), never evidence the code
            # itself is wrong. Keep this distinct from a genuine 401 rejection
            # so the two are never shown as the same "was rejected" message.
            raise CameraNodeClientError("pairing_code_already_used")
        if status == 401:
            raise CameraNodeClientError("pairing_rejected")
        if status != 200:
            raise CameraNodeClientError("node_unavailable")
        body = _safe_json(data)
        node_id, display_name, api_version, credential = body.get("node_id"), body.get("display_name"), body.get("api_version"), body.get("credential")
        if not all(isinstance(value, str) and value and len(value) <= 160 for value in (node_id, display_name, api_version, credential)):
            raise CameraNodeClientError("node_response_invalid")
        if api_version != NODE_API_VERSION:
            raise CameraNodeClientError("node_api_unsupported")
        try:
            capabilities = self.capabilities(base_address=base, credential=credential)
        except CameraNodeClientError:
            # Capability timing is optional protocol metadata. A paired old Node
            # remains compatible with the main app's fixed cold-start allowance.
            capabilities = {}
        return CameraNodePairing(
            base,
            node_id,
            display_name,
            api_version,
            credential,
            _camera_items(body.get("cameras")),
            secrets.token_hex(16),
            _recommended_snapshot_timeout(capabilities.get("recommended_snapshot_timeout_seconds")),
            _transport_credential(body.get("transport_credential")),
        )

    def capabilities(self, *, base_address: str, credential: str) -> dict[str, Any]:
        base = normalize_camera_node_address(base_address)
        status, _, data = self._request(
            base_address=base,
            path="/node/v1/capabilities",
            credential=credential,
        )
        if status == 401:
            raise CameraNodeClientError("authentication_rejected")
        if status != 200:
            raise CameraNodeClientError("node_unavailable")
        return _safe_json(data)

    def cameras(self, *, base_address: str, credential: str) -> list[CameraNodeCamera]:
        base = normalize_camera_node_address(base_address)
        status, _, data = self._request(base_address=base, path="/node/v1/cameras", credential=credential)
        if status == 401:
            raise CameraNodeClientError("authentication_rejected")
        if status != 200:
            raise CameraNodeClientError("node_unavailable")
        return _camera_items(_safe_json(data).get("items"))

    def snapshot(
        self,
        *,
        base_address: str,
        credential: str,
        camera_id: str,
        recommended_timeout_seconds: float | None = None,
    ) -> bytes:
        base = normalize_camera_node_address(base_address)
        if not camera_id or len(camera_id) > 120 or "/" in camera_id:
            raise CameraNodeClientError("node_camera_not_allowed")
        status, headers, data = self._request(
            base_address=base,
            path=f"/node/v1/cameras/{camera_id}/snapshot",
            credential=credential,
            max_bytes=MAX_NODE_SNAPSHOT_BYTES,
            timing=_snapshot_timing(recommended_timeout_seconds),
        )
        if status == 401:
            raise CameraNodeClientError("authentication_rejected")
        node_error = headers.get(_NODE_SNAPSHOT_ERROR_HEADER, headers.get(_NODE_SNAPSHOT_ERROR_HEADER.lower(), ""))
        if node_error in _NODE_SNAPSHOT_ERROR_CODES:
            raise CameraNodeClientError(
                _NODE_SNAPSHOT_ERROR_ALIASES.get(node_error, node_error)
            )
        if status in {404, 409}:
            raise CameraNodeClientError("node_camera_unavailable")
        if status != 200:
            raise CameraNodeClientError("node_unavailable")
        content_type = headers.get("Content-Type", headers.get("content-type", "")).split(";", 1)[0].lower()
        if content_type != "image/jpeg" or not data.startswith(b"\xff\xd8"):
            raise CameraNodeClientError("node_snapshot_invalid")
        return data

    def capture(
        self,
        *,
        base_address: str,
        credential: str,
        camera_id: str,
        profile: CameraNodeCaptureProfile,
    ) -> CameraNodeCapture:
        """Request one explicitly advertised evidence image with fixed bounds."""

        base = normalize_camera_node_address(base_address)
        if (
            not camera_id
            or len(camera_id) > 120
            or "/" in camera_id
            or not profile.profile_id
            or len(profile.profile_id) > 120
            or "/" in profile.profile_id
            or not profile.jpeg_supported
            or not (profile.supports_monitoring or profile.supports_evidence)
        ):
            raise CameraNodeClientError("node_capture_profile_unavailable")
        maximum_bytes = min(MAX_NODE_CAPTURE_BYTES, profile.max_expected_bytes)
        status, headers, data = self._request(
            base_address=base,
            path=f"/node/v1/cameras/{camera_id}/capture",
            method="POST",
            credential=credential,
            payload={"profile_id": profile.profile_id},
            max_bytes=maximum_bytes,
            timing=_snapshot_timing(),
        )
        if status == 401:
            raise CameraNodeClientError("authentication_rejected")
        node_error = headers.get(
            _NODE_SNAPSHOT_ERROR_HEADER,
            headers.get(_NODE_SNAPSHOT_ERROR_HEADER.lower(), ""),
        )
        if node_error in _NODE_SNAPSHOT_ERROR_CODES:
            raise CameraNodeClientError(
                _NODE_SNAPSHOT_ERROR_ALIASES.get(node_error, node_error)
            )
        if status in {404, 409}:
            raise CameraNodeClientError("node_capture_profile_unavailable")
        if status != 200:
            raise CameraNodeClientError("node_unavailable")
        content_type = headers.get("Content-Type", headers.get("content-type", "")).split(";", 1)[0].lower()
        dimensions = _jpeg_dimensions(data)
        returned_profile = headers.get(
            "X-MockingBird-Capture-Profile",
            headers.get("x-mockingbird-capture-profile"),
        )
        monitoring_recovery = headers.get(
            _NODE_MONITORING_RECOVERY_HEADER,
            headers.get(_NODE_MONITORING_RECOVERY_HEADER.lower()),
        )
        if monitoring_recovery not in _NODE_MONITORING_RECOVERY_STATES:
            monitoring_recovery = None
        if (
            content_type != "image/jpeg"
            or dimensions is None
            or dimensions[0] > profile.width
            or dimensions[1] > profile.height
            or returned_profile != profile.profile_id
        ):
            raise CameraNodeClientError("node_snapshot_invalid")
        return CameraNodeCapture(
            image=data,
            profile_id=profile.profile_id,
            captured_at=_captured_at_header(headers),
            width=dimensions[0],
            height=dimensions[1],
            monitoring_recovery=monitoring_recovery,
        )

    def revoke(self, *, base_address: str, credential: str) -> None:
        base = normalize_camera_node_address(base_address)
        status, _, _ = self._request(base_address=base, path="/node/v1/pair/revoke", method="POST", credential=credential)
        if status not in {204, 401}:
            raise CameraNodeClientError("node_unavailable")
