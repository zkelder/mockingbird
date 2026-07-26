"""Strict main-app client for one explicitly configured Camera Node address.

The client never discovers hosts, follows redirects, uses caller-provided paths,
or logs bearer credentials. Pairing is explicit; ordinary status reads do not
instantiate this client or contact a Node.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.client import HTTPConnection, HTTPSConnection
import ipaddress
import json
import secrets
import socket
import threading
import time
from typing import Any, Protocol
from urllib.parse import urlsplit, urlunsplit


NODE_API_VERSION = "v1"
MAX_NODE_JSON_BYTES = 128_000
MAX_NODE_SNAPSHOT_BYTES = 1_500_000
PAIRING_SESSION_TTL_SECONDS = 10 * 60
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
        "node_unavailable",
        "provider_reset_required",
    }
)

_NODE_SNAPSHOT_ERROR_HEADER = "X-MockingBird-Node-Error"
_NODE_SNAPSHOT_ERROR_CODES = frozenset(
    {
        "node_camera_warmup_timeout",
        "node_snapshot_invalid",
        "node_snapshot_timeout",
        "provider_reset_required",
    }
)


class CameraNodeClientError(ValueError):
    """Safe client error codes only; raw host/credential/transport text is discarded."""


@dataclass(frozen=True)
class CameraNodeCamera:
    camera_id: str
    display_name: str
    status: str
    snapshot_supported: bool
    setup_hint: str | None = None
    provider_type: str | None = None


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


@dataclass(frozen=True)
class CameraNodePairingSession:
    token: str
    pairing: CameraNodePairing
    expires_at: datetime


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
        if not all(isinstance(candidate, str) and candidate for candidate in (camera_id, display_name, status)) or len(camera_id) > 120 or len(display_name) > 120 or status not in {"available", "setup_required", "unavailable"}:
            raise CameraNodeClientError("node_response_invalid")
        hint, provider_type = item.get("setup_hint"), item.get("provider_type")
        cameras.append(CameraNodeCamera(camera_id, display_name, status, bool(item.get("snapshot_supported")), hint if isinstance(hint, str) and len(hint) <= 240 else None, provider_type if provider_type in {"v4l2", "picamera2", "synthetic", "local"} else None))
    return cameras


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

    def pair(self, base_address: str, pairing_code: str) -> CameraNodePairing:
        base = normalize_camera_node_address(base_address)
        code = pairing_code.strip()
        if not code or len(code) > 128:
            raise CameraNodeClientError("pairing_rejected")
        status, _, data = self._request(base_address=base, path="/node/v1/pair", method="POST", payload={"pairing_code": code})
        if status == 410:
            raise CameraNodeClientError("pairing_code_expired")
        if status == 429:
            raise CameraNodeClientError("pairing_rate_limited")
        if status in {401, 409}:
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
            raise CameraNodeClientError(node_error)
        if status in {404, 409}:
            raise CameraNodeClientError("node_camera_unavailable")
        if status != 200:
            raise CameraNodeClientError("node_unavailable")
        content_type = headers.get("Content-Type", headers.get("content-type", "")).split(";", 1)[0].lower()
        if content_type != "image/jpeg" or not data.startswith(b"\xff\xd8"):
            raise CameraNodeClientError("node_snapshot_invalid")
        return data

    def revoke(self, *, base_address: str, credential: str) -> None:
        base = normalize_camera_node_address(base_address)
        status, _, _ = self._request(base_address=base, path="/node/v1/pair/revoke", method="POST", credential=credential)
        if status not in {204, 401}:
            raise CameraNodeClientError("node_unavailable")


class CameraNodePairingStore:
    """Short-lived main-app handoff; it never returns a durable credential."""
    def __init__(self, *, ttl_seconds: int = PAIRING_SESSION_TTL_SECONDS) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._sessions: dict[str, CameraNodePairingSession] = {}
        self._lock = threading.RLock()

    def create(self, pairing: CameraNodePairing) -> CameraNodePairingSession:
        now = datetime.now(UTC)
        session = CameraNodePairingSession(f"node-pair-{secrets.token_urlsafe(24)}", pairing, now + self._ttl)
        with self._lock:
            self._purge(now)
            self._sessions[session.token] = session
        return session

    def consume(self, token: str, *, camera_id: str) -> CameraNodePairing | None:
        now = datetime.now(UTC)
        with self._lock:
            self._purge(now)
            session = self._sessions.get(token)
            if session is None:
                return None
            camera = next(
                (candidate for candidate in session.pairing.cameras if candidate.camera_id == camera_id),
                None,
            )
            if camera is None or camera.status != "available" or not camera.snapshot_supported:
                raise CameraNodeClientError("node_camera_not_allowed")
            return session.pairing

    def _purge(self, now: datetime) -> None:
        self._sessions = {token: session for token, session in self._sessions.items() if session.expires_at > now}
