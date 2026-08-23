"""Request correlation headers, API-version header, and the shared database-
failure exception handler (First-Hour Onboarding + Whole-Product
Observability Closure v1 -- "Correlation IDs" / "Stable structured error
taxonomy").

Mirrors test_product_health.py's own httpx.ASGITransport + `api_main.
_repository` monkeypatch convention rather than inventing a second one.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from sqlalchemy.exc import OperationalError
from starlette.requests import Request

from mockingbird import __version__ as APP_VERSION
from mockingbird.api import main as api_main
from mockingbird.api.main import _handle_database_error, app
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient


def _repository(tmp_path: Path) -> ProductRepository:
    return ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )


def _request(path: str, method: str = "GET") -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path)

    return asyncio.run(send())


@pytest.fixture
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ProductRepository:
    repository = _repository(tmp_path)
    monkeypatch.setattr(api_main, "_repository", repository)
    return repository


def test_every_response_carries_a_request_id_and_api_version_header(isolated_repository: ProductRepository) -> None:
    response = _request("/api/product/instance")
    assert response.status_code == 200
    assert response.headers.get("X-Request-Id")
    assert response.headers["X-MockingBird-Api-Version"] == APP_VERSION


def test_a_client_supplied_request_id_is_echoed_back(isolated_repository: ProductRepository) -> None:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/api/product/instance", headers={"X-Request-Id": "support-ticket-1234"})

    response = asyncio.run(send())
    assert response.headers["X-Request-Id"] == "support-ticket-1234"


def test_an_oversized_client_supplied_request_id_is_replaced_not_echoed(
    isolated_repository: ProductRepository,
) -> None:
    """A caller must not be able to smuggle an unbounded string into a log
    line/correlation field through this header."""

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as client:
            return await client.get("/api/product/instance", headers={"X-Request-Id": "x" * 500})

    response = asyncio.run(send())
    assert response.headers["X-Request-Id"] != "x" * 500
    assert len(response.headers["X-Request-Id"]) <= 128


def test_two_different_requests_get_two_different_generated_request_ids(
    isolated_repository: ProductRepository,
) -> None:
    first = _request("/api/product/instance")
    second = _request("/api/product/instance")
    assert first.headers["X-Request-Id"] != second.headers["X-Request-Id"]


def test_database_error_from_a_route_produces_a_structured_500_never_a_raw_500(
    isolated_repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real, uncaught `SQLAlchemyError` from a route handler -- exactly
    the class of failure the observability inventory found zero handling
    for anywhere in the 32k-line repository module -- must produce the
    shared structured response, not FastAPI's bare unhandled-exception 500."""

    def _broken_list_sources() -> list:
        raise OperationalError("SELECT * FROM sources", {}, Exception("disk I/O error"))

    monkeypatch.setattr(isolated_repository, "list_sources", _broken_list_sources)

    response = _request("/api/sources")

    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "storage_write_failed"
    assert body["error"]["component"] == "database"
    assert body["error"]["recoverability"] == "degraded"
    assert body["error"]["retryable"] is True
    # User-safe: the raw SQL statement and the underlying "disk I/O error"
    # must never appear in the always-shown `detail`/`message`.
    assert "SELECT" not in body["detail"]
    assert "disk I/O error" not in body["detail"]
    assert "SELECT" not in body["error"]["message"]
    # ...but a bounded, advanced-only summary is still available for
    # support/log correlation, matching Doctor's own precedent.
    assert "OperationalError" in body["error"]["diagnostic"]["exception"]
    assert response.headers.get("X-Request-Id")


def test_handler_correlates_the_request_id_that_generated_it() -> None:
    """Direct unit-level check of the handler itself (mirrors this file's
    other tests exercising it indirectly through a full HTTP round trip):
    the same request_id the middleware attached to `request.state` must
    appear in the structured error body's own correlation, not just the
    response header."""

    scope = {"type": "http", "method": "GET", "path": "/api/sources", "headers": []}
    request = Request(scope)
    request.state.request_id = "unit-test-request-id"

    async def call() -> object:
        return await _handle_database_error(request, OperationalError("SELECT 1", {}, Exception("boom")))

    response = asyncio.run(call())

    import json

    body = json.loads(bytes(response.body))
    assert body["error"]["correlation"]["request_id"] == "unit-test-request-id"
