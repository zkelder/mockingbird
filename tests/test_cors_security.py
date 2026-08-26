"""CORS configuration -- regression coverage for a real, previously-untested
security boundary (Mobile & Remote Experience v1's Phase 28 security check).

`src/mockingbird/api/main.py`'s single `CORSMiddleware` registration had no
dedicated test anywhere in this suite before this file (confirmed by a
repository-wide grep for `CORSMiddleware`/`allow_origins` under `tests/`).
This does not fix a defect -- the configuration was already a bounded,
explicit allowlist, never a wildcard -- it closes the coverage gap so a
future change (for example, someone "fixing" a LAN/remote-access CORS
complaint by widening `allow_origins` to `"*"` while `allow_credentials=
True` stays set, the textbook CORS misconfiguration) fails loudly here
instead of silently shipping.
"""

from __future__ import annotations

import httpx
import pytest

from mockingbird.api.main import app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def test_allow_origins_is_never_a_wildcard_while_credentials_are_allowed() -> None:
    """Static assertion against the actual installed middleware config, not
    just a behavioral probe -- catches the misconfiguration even before a
    browser/httpx request would."""

    cors_middleware = next(
        m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware"
    )
    options = cors_middleware.kwargs
    assert options["allow_credentials"] is True
    assert options["allow_origins"] != ["*"]
    assert "*" not in options["allow_origins"]
    # Every entry is a real, bounded origin (scheme + host + port), never an
    # accidentally-broad pattern.
    for origin in options["allow_origins"]:
        assert origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:")


@pytest.mark.anyio
async def test_an_allowed_dev_origin_receives_real_cors_headers() -> None:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.anyio
async def test_an_arbitrary_origin_receives_no_cors_grant() -> None:
    """The actual security property: an untrusted origin's request is not
    silently denied at the HTTP layer (CORS is a browser-enforced
    contract, not a server-side access-control mechanism, and `/health` is
    intentionally public), but it never receives an `Access-Control-Allow-
    Origin` telling a browser it may read the response cross-origin --
    exactly what stops an unrelated malicious page from reading this API
    using a victim's browser session cookie."""

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/health", headers={"Origin": "https://evil.example.com"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers.keys()}


@pytest.mark.anyio
async def test_an_arbitrary_origin_preflight_is_not_granted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real cross-origin attack surface: a browser's own CORS
    preflight (`OPTIONS` + `Access-Control-Request-Method`) for a
    credentialed, non-simple request (matching how the real frontend calls
    the API) must not be granted for an untrusted origin."""

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.options(
            "/api/streams",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )
    assert "access-control-allow-origin" not in {k.lower() for k in response.headers.keys()}
