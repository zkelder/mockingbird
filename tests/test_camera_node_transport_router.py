"""Tier 1/2: the host transport router's HTTP boundary.

Real FastAPI routing/validation via `httpx.ASGITransport` (in-process, no
real sockets -- matches this codebase's existing Camera Node test
convention), with a fake `resolve_transport_source` so this stays
independent of `ProductRepository`. Confirms the exact
`{"detail": {"error_code": ...}}` response shape
`mockingbird_node.transport_client._error_code` depends on.
"""

from __future__ import annotations

import hashlib

from fastapi import FastAPI
import httpx
import pytest

from mockingbird.api.camera_node_transport import TRANSPORT_PROTOCOL_VERSION, build_camera_node_transport_router


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _app(tmp_path, *, sources=None):
    sources = sources or {"good-credential": ("source-1", "node-1")}

    def resolve(credential: str):
        return sources.get(credential)

    app = FastAPI()
    app.include_router(build_camera_node_transport_router(resolve_transport_source=resolve, transport_root=tmp_path / "transport"))
    return app


def _declare_payload(*, node_id="node-1", item_id="item-1", content_length=4, content_sha256=None, chunk_size=1024):
    return {
        "transport_protocol_version": TRANSPORT_PROTOCOL_VERSION,
        "node_id": node_id,
        "item_id": item_id,
        "kind": "evidence_capture",
        "priority": 100,
        "media_type": "image/jpeg",
        "content_length": content_length,
        "content_sha256": content_sha256 or hashlib.sha256(b"x" * content_length).hexdigest(),
        "chunk_size": chunk_size,
        "metadata": {"camera_id": "cam-1"},
        "backlog_summary": {"pending_count": 0},
    }


@pytest.mark.anyio
async def test_declare_without_authorization_header_is_401(tmp_path) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(tmp_path)), base_url="http://test") as client:
        response = await client.post("/api/camera-nodes/transport/items", json=_declare_payload())
    assert response.status_code == 401
    assert response.json()["detail"]["error_code"] == "authentication_rejected"


@pytest.mark.anyio
async def test_declare_with_unknown_credential_is_401(tmp_path) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(tmp_path)), base_url="http://test") as client:
        response = await client.post(
            "/api/camera-nodes/transport/items",
            json=_declare_payload(),
            headers={"Authorization": "Bearer wrong-credential"},
        )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_declare_with_node_id_not_matching_resolved_source_is_401(tmp_path) -> None:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(tmp_path)), base_url="http://test") as client:
        response = await client.post(
            "/api/camera-nodes/transport/items",
            json=_declare_payload(node_id="a-different-node"),
            headers={"Authorization": "Bearer good-credential"},
        )
    assert response.status_code == 401


@pytest.mark.anyio
async def test_declare_with_unsupported_protocol_version_is_400(tmp_path) -> None:
    payload = _declare_payload()
    payload["transport_protocol_version"] = "transport/v99"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(tmp_path)), base_url="http://test") as client:
        response = await client.post(
            "/api/camera-nodes/transport/items", json=payload, headers={"Authorization": "Bearer good-credential"}
        )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "transport_protocol_unsupported"


@pytest.mark.anyio
async def test_full_declare_chunk_complete_flow_over_real_http(tmp_path) -> None:
    payload_bytes = b"abcd"
    headers = {"Authorization": "Bearer good-credential"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(tmp_path)), base_url="http://test") as client:
        declare_response = await client.post(
            "/api/camera-nodes/transport/items",
            json=_declare_payload(content_length=4, content_sha256=hashlib.sha256(payload_bytes).hexdigest(), chunk_size=1024),
            headers=headers,
        )
        assert declare_response.status_code == 200
        assert declare_response.json() == {"status": "accepted", "received_bytes": 0}

        chunk_response = await client.post(
            "/api/camera-nodes/transport/items/item-1/chunks/0",
            content=payload_bytes,
            headers={**headers, "X-MockingBird-Chunk-Sha256": hashlib.sha256(payload_bytes).hexdigest()},
        )
        assert chunk_response.status_code == 200
        assert chunk_response.json() == {"status": "received", "received_bytes": 4}

        complete_response = await client.post("/api/camera-nodes/transport/items/item-1/complete", headers=headers)
        assert complete_response.status_code == 200
        assert complete_response.json() == {"status": "completed"}

        status_response = await client.get("/api/camera-nodes/transport/items/item-1", headers=headers)
        assert status_response.status_code == 200
        assert status_response.json()["state"] == "completed"

        # A retried declare after completion is a clean duplicate, not a re-upload.
        redeclare_response = await client.post(
            "/api/camera-nodes/transport/items",
            json=_declare_payload(content_length=4, content_sha256=hashlib.sha256(payload_bytes).hexdigest(), chunk_size=1024),
            headers=headers,
        )
        assert redeclare_response.json() == {"status": "duplicate", "received_bytes": 4}


@pytest.mark.anyio
async def test_chunk_hash_mismatch_returns_400_with_error_code(tmp_path) -> None:
    headers = {"Authorization": "Bearer good-credential"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(tmp_path)), base_url="http://test") as client:
        await client.post("/api/camera-nodes/transport/items", json=_declare_payload(), headers=headers)
        response = await client.post(
            "/api/camera-nodes/transport/items/item-1/chunks/0",
            content=b"abcd",
            headers={**headers, "X-MockingBird-Chunk-Sha256": "0" * 64},
        )
    assert response.status_code == 400
    assert response.json()["detail"]["error_code"] == "transport_chunk_hash_mismatch"


@pytest.mark.anyio
async def test_unknown_item_status_is_404(tmp_path) -> None:
    headers = {"Authorization": "Bearer good-credential"}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=_app(tmp_path)), base_url="http://test") as client:
        response = await client.get("/api/camera-nodes/transport/items/never-declared", headers=headers)
    assert response.status_code == 404
    assert response.json()["detail"]["error_code"] == "transport_item_unknown"


@pytest.mark.anyio
async def test_two_different_nodes_do_not_see_each_others_items(tmp_path) -> None:
    app = _app(tmp_path, sources={"cred-a": ("source-a", "node-a"), "cred-b": ("source-b", "node-b")})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/camera-nodes/transport/items",
            json=_declare_payload(node_id="node-a", item_id="shared-item-id"),
            headers={"Authorization": "Bearer cred-a"},
        )
        # Node B declaring the *same* item_id is a fresh item under its own
        # node_id namespace, not a collision with Node A's.
        response = await client.post(
            "/api/camera-nodes/transport/items",
            json=_declare_payload(node_id="node-b", item_id="shared-item-id"),
            headers={"Authorization": "Bearer cred-b"},
        )
    assert response.status_code == 200
    assert response.json() == {"status": "accepted", "received_bytes": 0}
