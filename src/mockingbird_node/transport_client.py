"""Outbound Node -> host delivery: the declare / chunk / complete protocol.

Mirrors `source_providers.camera_node.UrlLibCameraNodeRequester`'s existing
style deliberately (stdlib `http.client`, no new runtime dependency for a
Pi-class device, bounded connect/response timeouts, one connection per
call) even though this is the opposite direction on the wire. See
docs/remote-intermittent-wan-transport-v1-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from http.client import HTTPConnection, HTTPSConnection
import hashlib
import json
import socket
import time
from typing import Any, Protocol
from urllib.parse import urlsplit

from .transport_spool import SpoolItem


TRANSPORT_PROTOCOL_VERSION = "transport/v1"
TRANSPORT_CONNECT_TIMEOUT_SECONDS = 3.0
TRANSPORT_RESPONSE_TIMEOUT_SECONDS = 10.0
MAX_TRANSPORT_RESPONSE_BYTES = 64_000

# Per-item: retrying the identical request can never succeed, so further
# attempts would spin forever for no benefit (Scenario 8).
TERMINAL_TRANSPORT_ERROR_CODES = frozenset({"transport_item_conflict"})

# Node-wide conditions: retrying *this* item with backoff is still correct
# (an operator can fix the underlying cause -- re-pair, upgrade the host --
# without losing already-spooled evidence), but they are distinct enough
# from ordinary connectivity flakiness that the worker tracks them as a
# separate, sticky, prominently-surfaced diagnostic. See the design doc's
# "Compatibility/version handling" -- deliberately not folded into
# `TERMINAL_TRANSPORT_ERROR_CODES`.
STICKY_DIAGNOSTIC_ERROR_CODES = frozenset(
    {"transport_protocol_unsupported", "authentication_rejected"}
)


class TransportClientError(ValueError):
    """Safe, bounded transport error codes only -- never raw host/credential text."""


@dataclass(frozen=True)
class DeclareOutcome:
    duplicate: bool
    received_bytes: int


@dataclass(frozen=True)
class DeliveryOutcome:
    item_id: str
    delivered: bool
    error: str | None = None


class TransportRequester(Protocol):
    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, dict[str, str], bytes]: ...


class UrlLibTransportRequester:
    """One connection per call, bounded connect/response windows.

    Deliberately not pooled/reused across calls -- same reasoning already
    documented for the host->node direction (see
    docs/camera-node-connectivity-recovery-diagnosis-v1-report.md): a
    reused connection to a flaky/rotating remote path risks silently
    reusing a half-dead socket, which is worse for a bounded-retry design
    than the small per-call connection-setup cost.
    """

    def __init__(
        self,
        *,
        connect_timeout_seconds: float = TRANSPORT_CONNECT_TIMEOUT_SECONDS,
        response_timeout_seconds: float = TRANSPORT_RESPONSE_TIMEOUT_SECONDS,
    ) -> None:
        # Overridable only for deterministic fault-injection tests that
        # prove a real bounded timeout fires (see
        # tests/_transport_fault_injection.py) -- production always uses
        # the module defaults above.
        self._connect_timeout_seconds = connect_timeout_seconds
        self._response_timeout_seconds = response_timeout_seconds

    def _connection(self, url: str) -> tuple[HTTPConnection | HTTPSConnection, str]:
        parsed = urlsplit(url)
        path = parsed.path or "/"
        if parsed.scheme == "http":
            return HTTPConnection(parsed.netloc, timeout=self._connect_timeout_seconds), path
        if parsed.scheme == "https":
            return HTTPSConnection(parsed.netloc, timeout=self._connect_timeout_seconds), path
        raise TransportClientError("transport_endpoint_invalid")

    def request(
        self,
        *,
        method: str,
        url: str,
        headers: dict[str, str],
        body: bytes | None,
    ) -> tuple[int, dict[str, str], bytes]:
        connection: HTTPConnection | HTTPSConnection | None = None
        try:
            connection, path = self._connection(url)
            try:
                connection.request(method, path, body=body, headers=headers)
            except (socket.timeout, TimeoutError, OSError) as error:
                raise TransportClientError("transport_host_unreachable") from error
            try:
                if connection.sock is not None:
                    connection.sock.settimeout(self._response_timeout_seconds)
                response = connection.getresponse()
                data = response.read(MAX_TRANSPORT_RESPONSE_BYTES + 1)
            except (socket.timeout, TimeoutError) as error:
                raise TransportClientError("transport_host_timeout") from error
            except OSError as error:
                raise TransportClientError("transport_host_unreachable") from error
            if len(data) > MAX_TRANSPORT_RESPONSE_BYTES:
                raise TransportClientError("transport_response_invalid")
            return response.status, dict(response.headers.items()), data
        finally:
            if connection is not None:
                connection.close()


def _safe_json(data: bytes) -> dict[str, Any]:
    try:
        decoded = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise TransportClientError("transport_response_invalid") from error
    if not isinstance(decoded, dict):
        raise TransportClientError("transport_response_invalid")
    return decoded


def _error_code(body: dict[str, Any]) -> str | None:
    """The host's error responses nest `error_code` under `detail` (FastAPI's
    default exception handler wraps `HTTPException.detail` verbatim as
    `{"detail": ...}`) -- see `api.camera_node_transport._error`."""

    detail = body.get("detail")
    if isinstance(detail, dict):
        code = detail.get("error_code")
        return code if isinstance(code, str) else None
    return None


class TransportClient:
    """Delivers one `SpoolItem` to the host via declare / chunk(s) / complete."""

    def __init__(self, *, requester: TransportRequester | None = None) -> None:
        self._requester = requester or UrlLibTransportRequester()

    def _post_json(
        self, *, base_address: str, path: str, credential: str, payload: dict[str, Any]
    ) -> tuple[int, dict[str, Any]]:
        status, _, data = self._requester.request(
            method="POST",
            url=f"{base_address}{path}",
            headers={
                "Authorization": f"Bearer {credential}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Cache-Control": "no-store",
            },
            body=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        )
        return status, _safe_json(data) if data else {}

    def _raise_for_status(self, status: int, body: dict[str, Any]) -> None:
        if status == 401:
            raise TransportClientError("authentication_rejected")
        code = _error_code(body)
        if status == 400 and code == "transport_protocol_unsupported":
            raise TransportClientError("transport_protocol_unsupported")
        if status == 409 and code == "transport_item_conflict":
            raise TransportClientError("transport_item_conflict")
        if status >= 500:
            raise TransportClientError("transport_host_error")
        if status >= 400:
            raise TransportClientError(code or "transport_host_error")

    def declare(
        self,
        *,
        base_address: str,
        credential: str,
        node_id: str,
        item: SpoolItem,
        chunk_size: int,
        backlog_summary: dict[str, Any],
    ) -> DeclareOutcome:
        status, body = self._post_json(
            base_address=base_address,
            path="/api/camera-nodes/transport/items",
            credential=credential,
            payload={
                "transport_protocol_version": TRANSPORT_PROTOCOL_VERSION,
                "node_id": node_id,
                "item_id": item.item_id,
                "kind": item.kind,
                "priority": item.priority,
                "media_type": item.media_type,
                "content_length": item.content_length,
                "content_sha256": item.content_sha256,
                "chunk_size": chunk_size,
                "metadata": item.metadata,
                "backlog_summary": backlog_summary,
            },
        )
        self._raise_for_status(status, body)
        if body.get("status") == "duplicate":
            return DeclareOutcome(duplicate=True, received_bytes=item.content_length)
        received_bytes = body.get("received_bytes", 0)
        if not isinstance(received_bytes, int) or received_bytes < 0:
            raise TransportClientError("transport_response_invalid")
        return DeclareOutcome(duplicate=False, received_bytes=received_bytes)

    def send_chunk(
        self,
        *,
        base_address: str,
        credential: str,
        item_id: str,
        chunk_index: int,
        chunk: bytes,
    ) -> int:
        status, _, data = self._requester.request(
            method="POST",
            url=f"{base_address}/api/camera-nodes/transport/items/{item_id}/chunks/{chunk_index}",
            headers={
                "Authorization": f"Bearer {credential}",
                "Content-Type": "application/octet-stream",
                "X-MockingBird-Chunk-Sha256": hashlib.sha256(chunk).hexdigest(),
                "Cache-Control": "no-store",
            },
            body=chunk,
        )
        body = _safe_json(data) if data else {}
        self._raise_for_status(status, body)
        received_bytes = body.get("received_bytes")
        if not isinstance(received_bytes, int) or received_bytes < 0:
            raise TransportClientError("transport_response_invalid")
        return received_bytes

    def complete(self, *, base_address: str, credential: str, item_id: str) -> None:
        status, body = self._post_json(
            base_address=base_address,
            path=f"/api/camera-nodes/transport/items/{item_id}/complete",
            credential=credential,
            payload={},
        )
        if status in {409, 422} and _error_code(body) == "transport_item_hash_mismatch":
            raise TransportClientError("transport_item_hash_mismatch")
        self._raise_for_status(status, body)
        if body.get("status") != "completed":
            raise TransportClientError("transport_response_invalid")

    def deliver(
        self,
        *,
        base_address: str,
        credential: str,
        node_id: str,
        item: SpoolItem,
        payload: bytes,
        chunk_size: int,
        backlog_summary: dict[str, Any],
        max_bytes_per_second: int = 0,
        should_abort=lambda: False,
    ) -> None:
        """Deliver one item end-to-end. Raises `TransportClientError` on any
        failure; the caller (the worker) classifies and records it."""

        outcome = self.declare(
            base_address=base_address,
            credential=credential,
            node_id=node_id,
            item=item,
            chunk_size=chunk_size,
            backlog_summary=backlog_summary,
        )
        if outcome.duplicate:
            return
        offset = outcome.received_bytes
        index = offset // chunk_size
        while offset < len(payload):
            if should_abort():
                raise TransportClientError("transport_delivery_aborted")
            chunk = payload[offset : offset + chunk_size]
            _pace(len(chunk), max_bytes_per_second)
            received_bytes = self.send_chunk(
                base_address=base_address,
                credential=credential,
                item_id=item.item_id,
                chunk_index=index,
                chunk=chunk,
            )
            offset = received_bytes
            index += 1
        self.complete(base_address=base_address, credential=credential, item_id=item.item_id)


def _pace(chunk_bytes: int, max_bytes_per_second: int) -> None:
    """Simple sleep-based pacing: sleep long enough that this chunk, on its
    own, does not exceed the configured rate. Deliberately not a token
    bucket across the whole worker -- see the design doc's "Bandwidth-aware
    policy": the goal is a clean boundary, not an adaptive optimizer."""

    if max_bytes_per_second <= 0:
        return
    minimum_seconds = chunk_bytes / max_bytes_per_second
    if minimum_seconds > 0:
        time.sleep(minimum_seconds)


def classify_error(error: TransportClientError) -> str:
    code = str(error)
    if code in TERMINAL_TRANSPORT_ERROR_CODES:
        return "terminal"
    return "retryable"
