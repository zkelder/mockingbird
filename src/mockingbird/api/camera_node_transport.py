"""Host-side receiver for Remote / Intermittent-WAN Transport Foundation v1.

Node -> host delivery: declare / chunk / complete. This module owns exactly
that surface and nothing else -- no Observation authority, no Evidence/
Source schema, no host migration (see
docs/remote-intermittent-wan-transport-v1-design.md). It is a separate
`APIRouter` (composed into `main.py` with one `include_router` call) rather
than more inline endpoints on `main.py`'s single `FastAPI()` instance,
specifically to keep this branch's footprint in that large, concurrently
-edited file to a minimum -- see the design doc's closing decision.

The durable filesystem ledger itself lives in
`mockingbird.storage.camera_node_transport_ledger` (no HTTP-framework
dependency, so `diagnostics.doctor` can read it without inverting this
codebase's layering); this module is the thin HTTP boundary that translates
`TransportLedgerError` into the right `HTTPException`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from mockingbird.diagnostics.structured_log import log_error_event

from mockingbird.storage.camera_node_transport_ledger import (
    TransportLedger,
    TransportLedgerError,
    resolve_transport_root,
)


# Duplicated (not imported) on purpose: `mockingbird_node` is a separate
# package, built and shipped independently for a Pi-class device (see
# `scripts/build_camera_node_artifact.py`), and no file under
# `src/mockingbird_node/` imports from the main `mockingbird` package today
# -- host code returning the favor would create the one coupling that
# currently doesn't exist. This mirrors the codebase's own existing
# precedent: `NODE_API_VERSION` is already two independently-maintained
# `"v1"` constants, one per side (see `source_providers/camera_node.py` and
# `mockingbird_node/app.py`), not a shared import.
TRANSPORT_PROTOCOL_VERSION = "transport/v1"


class TransportDeclareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    transport_protocol_version: str = Field(min_length=1, max_length=40)
    node_id: str = Field(min_length=1, max_length=160)
    item_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    kind: str = Field(min_length=1, max_length=60, pattern=r"^[A-Za-z0-9_.:-]+$")
    priority: int = Field(ge=0, le=1000)
    media_type: str = Field(min_length=1, max_length=80)
    content_length: int = Field(ge=0, le=64_000_000)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_size: int = Field(ge=1024, le=8_000_000)
    metadata: dict[str, Any] = Field(default_factory=dict)
    backlog_summary: dict[str, Any] = Field(default_factory=dict)


class TransportDeclareResponse(BaseModel):
    status: str
    received_bytes: int


class TransportChunkResponse(BaseModel):
    status: str
    received_bytes: int


class TransportCompleteResponse(BaseModel):
    status: str


class TransportItemStatusResponse(BaseModel):
    item_id: str
    state: str
    received_bytes: int
    content_length: int


def _http_error(error: TransportLedgerError) -> HTTPException:
    # `detail` is a dict, not a string: FastAPI's default exception handler
    # serializes it verbatim as `{"detail": ...}`, so the response body ends
    # up `{"detail": {"error_code": ..., "message": ...}}` -- that is what
    # `mockingbird_node.transport_client`'s `_error_code` reads. The header
    # is a convenience for a human reading raw `curl -v` output, not itself
    # load-bearing.
    return HTTPException(
        status_code=error.status_code,
        detail={"error_code": error.error_code, "message": error.message},
        headers={"X-MockingBird-Error-Code": error.error_code},
    )


def _auth_error() -> HTTPException:
    return _http_error(TransportLedgerError(401, "authentication_rejected", "Transport authentication is required."))


@dataclass(frozen=True)
class _ResolvedSource:
    source_id: str
    node_id: str


def build_camera_node_transport_router(
    *,
    resolve_transport_source: Callable[[str], tuple[str, str] | None],
    transport_root: Path | None = None,
    on_item_completed: Callable[[str, str], None] | None = None,
) -> APIRouter:
    """Factory, not a module-level router: takes `resolve_transport_source`
    (normally `ProductRepository.resolve_camera_node_transport_source`) as
    a plain callable so this module never imports `mockingbird.api.main`
    (which imports *this* module) -- avoids a circular import while keeping
    this router fully unit-testable with a fake resolver.

    `on_item_completed` (Appliance / Storage / Privacy / Recovery v1,
    Phase E), normally `ProductRepository.consume_camera_node_transport_item`,
    is called with `(node_id, item_id)` immediately after a `complete`
    call durably completes an item -- the one hook point where this
    otherwise Evidence/Observation-agnostic transport surface hands a
    completed item off to the product's real ingest path. Any exception it
    raises is caught and logged here, never surfaced to the Node: the item
    is already durably "completed," and the Node deletes its own spooled
    copy the instant it sees a 200 response, so a consumption failure must
    be recovered by the host's own later sweep, never by asking the Node to
    resend bytes it no longer has. `None` (the default) leaves this router
    exactly as receive-only as before this milestone -- used by tests that
    only exercise the declare/chunk/complete protocol itself."""

    ledger = TransportLedger(resolve_transport_root(transport_root))
    router = APIRouter(prefix="/api/camera-nodes/transport", tags=["camera-node-transport"])

    def require_transport_source(authorization: str) -> _ResolvedSource:
        prefix, _, credential = authorization.partition(" ")
        if prefix.lower() != "bearer" or not credential:
            raise _auth_error()
        match = resolve_transport_source(credential)
        if match is None:
            raise _auth_error()
        source_id, node_id = match
        return _ResolvedSource(source_id=source_id, node_id=node_id)

    @router.post("/items", response_model=TransportDeclareResponse)
    async def declare_item(payload: TransportDeclareRequest, request: Request) -> TransportDeclareResponse:
        source = require_transport_source(request.headers.get("authorization", ""))
        if payload.node_id != source.node_id:
            raise _auth_error()
        if payload.transport_protocol_version != TRANSPORT_PROTOCOL_VERSION:
            raise _http_error(
                TransportLedgerError(
                    400,
                    "transport_protocol_unsupported",
                    f"This host supports {TRANSPORT_PROTOCOL_VERSION!r} only.",
                )
            )
        try:
            if ledger.is_completed(source.node_id, payload.item_id):
                ledger.record_backlog_summary(node_id=source.node_id, summary=payload.backlog_summary)
                return TransportDeclareResponse(status="duplicate", received_bytes=payload.content_length)
            received = ledger.declare(
                node_id=source.node_id,
                item_id=payload.item_id,
                kind=payload.kind,
                priority=payload.priority,
                media_type=payload.media_type,
                content_length=payload.content_length,
                content_sha256=payload.content_sha256,
                chunk_size=payload.chunk_size,
                metadata=payload.metadata,
            )
        except TransportLedgerError as error:
            raise _http_error(error) from None
        ledger.record_backlog_summary(node_id=source.node_id, summary=payload.backlog_summary)
        return TransportDeclareResponse(status="accepted", received_bytes=received)

    @router.post("/items/{item_id}/chunks/{chunk_index}", response_model=TransportChunkResponse)
    async def upload_chunk(
        item_id: str,
        chunk_index: int,
        request: Request,
        x_mockingbird_chunk_sha256: str = Header(default=""),
    ) -> TransportChunkResponse:
        source = require_transport_source(request.headers.get("authorization", ""))
        if chunk_index < 0:
            raise _http_error(TransportLedgerError(400, "transport_chunk_index_invalid", "Invalid chunk index."))
        chunk = await request.body()
        try:
            received = ledger.write_chunk(
                node_id=source.node_id,
                item_id=item_id,
                chunk_index=chunk_index,
                chunk=chunk,
                declared_sha256=x_mockingbird_chunk_sha256,
            )
        except TransportLedgerError as error:
            raise _http_error(error) from None
        return TransportChunkResponse(status="received", received_bytes=received)

    @router.post("/items/{item_id}/complete", response_model=TransportCompleteResponse)
    async def complete_item(item_id: str, request: Request) -> TransportCompleteResponse:
        source = require_transport_source(request.headers.get("authorization", ""))
        try:
            ledger.complete(node_id=source.node_id, item_id=item_id)
        except TransportLedgerError as error:
            raise _http_error(error) from None
        # Appliance / Storage / Privacy / Recovery v1, Phase E: the item is
        # already durably "completed" on the ledger at this point -- the
        # Node is about to delete its own spooled copy the moment it sees
        # this 200 response (see `mockingbird_node.transport_worker`), so
        # consumption from here on is the host's own responsibility and
        # must never make the Node think delivery failed. Best-effort and
        # bounded: a consumption failure here is recovered by the next
        # startup sweep (`ProductRepository.consume_pending_camera_node_
        # transport_backlog`), never by asking the Node to resend bytes it
        # no longer has.
        if on_item_completed is not None:
            try:
                on_item_completed(source.node_id, item_id)
            except Exception as error:  # noqa: BLE001 - never fail the Node's ack on this
                log_error_event(
                    "camera_node_transport",
                    "item_consumption_failed",
                    code="camera_node_transport_consume_failed",
                    exception=error,
                    node_id=source.node_id,
                    item_id=item_id,
                )
        return TransportCompleteResponse(status="completed")

    @router.get("/items/{item_id}", response_model=TransportItemStatusResponse)
    async def item_status(item_id: str, request: Request) -> TransportItemStatusResponse:
        source = require_transport_source(request.headers.get("authorization", ""))
        result = ledger.status(node_id=source.node_id, item_id=item_id)
        if result is None:
            raise _http_error(TransportLedgerError(404, "transport_item_unknown", "No such item."))
        return TransportItemStatusResponse(
            item_id=result.item_id,
            state=result.state,
            received_bytes=result.received_bytes,
            content_length=result.content_length,
        )

    router.transport_ledger = ledger  # test/diagnostic access only, never itself an HTTP response
    return router
