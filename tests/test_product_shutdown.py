"""POST /api/product/shutdown: Release Reliability & First-Run Recovery v1's
graceful-stop UX contract.

The product's own two previously-documented stop methods (closing the
browser tab, which never reaches the backend at all; ending
`pythonw.exe`/`python.exe` in Task Manager, an external OS-level
termination no Python-level shutdown hook can reliably intercept) both left
the *next* launch honestly, but alarmingly, reporting "did not shut down
cleanly" -- even for an entirely deliberate, normal stop. This endpoint asks
the *same, still-running* process to stop itself gracefully instead, so it
can go through its own existing, already-correct `_app_lifespan` teardown
(unchanged by this endpoint -- see api/main.py), which already ends with
`mark_clean_shutdown()`.

Every test here runs against a bare test process, exactly like every other
HTTP test in this suite -- `app.state.uvicorn_server` is only ever set by
the real launch path in runtime.py, never by a test. The "no real server
available" case is therefore the *default*, ordinary state these tests
start from, not a specially-constructed edge case.
"""

from __future__ import annotations

from pathlib import Path
import types

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def _sign_in_as_administrator(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/setup/administrator",
        json={
            "display_name": "Ada Admin",
            "login_identity": "ada",
            "password": "correct horse battery",
        },
    )
    assert response.status_code == 201, response.text


async def test_shutdown_requires_signed_in_administrator(client: httpx.AsyncClient) -> None:
    """Never let an unauthenticated caller, or a signed-in non-Administrator,
    stop the whole Host -- at least as consequential as any camera/storage
    control already held to this same tier (see auth.py)."""

    unauthenticated = await client.post("/api/product/shutdown")
    assert unauthenticated.status_code == 401

    await _sign_in_as_administrator(client)
    created = await client.post(
        "/api/admin/users",
        json={
            "display_name": "Vic Viewer",
            "login_identity": "vic",
            "password": "viewer-password-1",
            "role": "viewer",
        },
    )
    assert created.status_code == 201, created.text

    viewer_transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=viewer_transport, base_url="http://testserver") as viewer_client:
        signed_in = await viewer_client.post(
            "/api/auth/sign-in", json={"login_identity": "vic", "password": "viewer-password-1"}
        )
        assert signed_in.status_code == 200

        forbidden = await viewer_client.post("/api/product/shutdown")
        assert forbidden.status_code == 403


async def test_shutdown_reports_not_accepted_when_no_server_is_running(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The honest degrade for a process not started through the real launch
    path -- every test in this suite, including this one. Never a crash,
    never a false claim that shutdown was requested when nothing can
    actually act on it."""

    monkeypatch.delattr(app.state, "uvicorn_server", raising=False)
    await _sign_in_as_administrator(client)

    response = await client.post("/api/product/shutdown")

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is False
    assert isinstance(body["message"], str) and body["message"]


async def test_shutdown_flips_the_running_servers_should_exit_flag(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The actual mechanism: a fake `Server`-shaped object (mirroring the
    one real attribute this endpoint reads on the real `uvicorn.Server`
    runtime.py publishes at `app.state.uvicorn_server`) has its
    `should_exit` flipped from `False` to `True` -- uvicorn's own
    documented in-process stop signal, noticed by its main loop on its very
    next iteration, driving the exact same graceful shutdown sequence an
    interactive terminal's Ctrl+C already triggers today. This deliberately
    never spins up a real `uvicorn.Server` (that is Tier D real-process
    acceptance, not a unit test) -- see
    `tests/test_single_app_runtime.py` for the real end-to-end proof."""

    fake_server = types.SimpleNamespace(should_exit=False)
    monkeypatch.setattr(app.state, "uvicorn_server", fake_server, raising=False)
    await _sign_in_as_administrator(client)

    response = await client.post("/api/product/shutdown")

    assert response.status_code == 200
    body = response.json()
    assert body["accepted"] is True
    assert "shutting down" in body["message"].lower()
    assert fake_server.should_exit is True


# This deliberately stops at the unit boundary above: confirming that a real
# `uvicorn.Server`, launched as a real OS process, actually stops when
# `should_exit` flips is Tier D real-process/real-hardware acceptance (see
# test-suite-validation-tiers-contract.md's "Tier D" -- no test in this
# suite spawns a real `python -m mockingbird` process, by established,
# deliberate convention: genuine hardware/process acceptance stays an
# explicit, bounded, stated-question procedure a developer runs
# deliberately, never folded into an ordinary pytest invocation). See the
# governing milestone's own closure report for that real verification.
