"""Non-Interactive Field Acceptance Authentication & Session Access v1 (see
docs/non-interactive-field-acceptance-authentication-session-access-v1-
contract.md).

Covers: provisioning (Administrator-only, explicit, never automatic);
bearer-token resolution (valid, unknown, malformed, revoked, expired -- all
distinct repository-level outcomes that collapse to the same generic 401
over HTTP, deliberately, mirroring `resolve_session`'s own non-disclosure
convention); the exact least-privilege authorization boundary (the Viewer
-floor read scope, plus the narrow Observation start/stop carve-out, and
nothing else Administrator- or Reviewer-tier); no-bypass regression
coverage (no header/localhost exemption, no anonymous fallback, a
low-privilege human session cannot combine with a bearer token to
escalate); revocation is immediate and deterministic; and auditability
(principal actions are distinguishable from a human Administrator's, no
secret ever logged).

Mirrors `tests/test_local_identity_multi_user.py`'s own established style
for this exact class of test: plain, unmodified `httpx.AsyncClient`
objects throughout (never `tests.conftest.LegacyAuthenticatedTestClient`),
real bootstrap, real sign-in, real un-masked 401/403 responses over real
HTTP -- this is one of the places that real, enforced policy must be
directly observable, not silently satisfied by test infrastructure.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import AdministratorBootstrapRequest, FieldAcceptanceCredentialCreate
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.security.passwords import generate_session_token, hash_session_token
from mockingbird.storage.models import FieldAcceptanceCredentialModel

pytestmark = pytest.mark.anyio

ADMIN_BODY = {"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"}


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


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
async def admin_client():
    """A signed-in Administrator -- the only identity allowed to provision
    or revoke a field-acceptance credential (see the governing contract's
    "Provisioning contract": always an already-authorized local
    administrative action, never automatic)."""

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        bootstrap = await api_client.post("/api/setup/administrator", json=ADMIN_BODY)
        assert bootstrap.status_code == 201, bootstrap.text
        yield api_client


async def bearer_client(token: str) -> httpx.AsyncClient:
    """A plain client carrying no cookie at all -- only the bearer token
    under test, via a real `Authorization` header, matching exactly how
    `scripts/field_acceptance_client.py` authenticates."""

    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(
        transport=transport, base_url="http://testserver", headers={"Authorization": f"Bearer {token}"}
    )


async def create_credential(
    admin_client: httpx.AsyncClient, *, label: str = "Field Acceptance Operator", expires_in_hours: int = 24
) -> dict:
    response = await admin_client.post(
        "/api/admin/field-acceptance-credentials",
        json={"label": label, "expires_in_hours": expires_in_hours},
    )
    assert response.status_code == 201, response.text
    return response.json()


# --- Provisioning is Administrator-only, explicit, never automatic ---------


async def test_only_administrator_can_create_field_acceptance_credential(
    admin_client: httpx.AsyncClient,
) -> None:
    unauthenticated = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=unauthenticated, base_url="http://testserver") as anon_client:
        response = await anon_client.post(
            "/api/admin/field-acceptance-credentials", json={"label": "x", "expires_in_hours": 24}
        )
        assert response.status_code == 401

    viewer_created = await admin_client.post(
        "/api/admin/users",
        json={"display_name": "Vic Viewer", "login_identity": "vic", "password": "viewer-password-1", "role": "viewer"},
    )
    assert viewer_created.status_code == 201
    viewer_transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=viewer_transport, base_url="http://testserver") as viewer_client:
        signed_in = await viewer_client.post(
            "/api/auth/sign-in", json={"login_identity": "vic", "password": "viewer-password-1"}
        )
        assert signed_in.status_code == 200
        response = await viewer_client.post(
            "/api/admin/field-acceptance-credentials", json={"label": "x", "expires_in_hours": 24}
        )
        assert response.status_code == 403

    created = await create_credential(admin_client)
    assert created["label"] == "Field Acceptance Operator"
    assert "token" in created and len(created["token"]) > 20


async def test_new_installation_has_no_field_acceptance_credential(admin_client: httpx.AsyncClient) -> None:
    """Not created automatically on normal installs -- see the governing
    contract's "Provisioning contract"."""

    listing = await admin_client.get("/api/admin/field-acceptance-credentials")
    assert listing.status_code == 200
    assert listing.json() == []


async def test_list_never_includes_the_raw_token_or_its_hash(admin_client: httpx.AsyncClient) -> None:
    await create_credential(admin_client)
    listing = await admin_client.get("/api/admin/field-acceptance-credentials")
    assert listing.status_code == 200
    entries = listing.json()
    assert len(entries) == 1
    assert "token" not in entries[0]
    assert "token_hash" not in entries[0]
    assert set(entries[0]) == {
        "id", "label", "created_at", "created_by_user_id", "created_by_display_name",
        "expires_at", "revoked_at", "last_used_at",
    }


async def test_credential_creation_is_recorded_with_the_provisioning_administrator_as_actor(
    admin_client: httpx.AsyncClient,
) -> None:
    created = await create_credential(admin_client)
    audit = await admin_client.get("/api/admin/audit-log")
    assert audit.status_code == 200
    entry = next(e for e in audit.json() if e["action"] == "field_acceptance_credential.created")
    assert entry["actor_display_name"] == "Ada Admin"
    assert entry["actor_user_id"] is not None
    assert entry["target_id"] == created["id"]
    metadata_text = str(entry.get("metadata"))
    assert created["token"] not in metadata_text


# --- Bearer-token resolution (repository level) -----------------------------


def test_resolve_field_acceptance_token_succeeds_for_a_valid_credential(
    isolated_repository: ProductRepository,
) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(
            display_name="Ada Admin", login_identity="ada", password="correct horse battery"
        )
    )
    summary, token = isolated_repository.create_field_acceptance_credential(
        FieldAcceptanceCredentialCreate(label="Field Acceptance Operator", expires_in_hours=24),
        acting_user=admin,
    )
    principal = isolated_repository.resolve_field_acceptance_token(token)
    assert principal is not None
    assert principal.id == summary.id
    assert principal.label == "Field Acceptance Operator"


def test_resolve_field_acceptance_token_returns_none_for_unknown_or_empty_token(
    isolated_repository: ProductRepository,
) -> None:
    assert isolated_repository.resolve_field_acceptance_token("not-a-real-token") is None
    assert isolated_repository.resolve_field_acceptance_token("") is None


def test_resolve_field_acceptance_token_returns_none_once_revoked(
    isolated_repository: ProductRepository,
) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    summary, token = isolated_repository.create_field_acceptance_credential(
        FieldAcceptanceCredentialCreate(label="op", expires_in_hours=24), acting_user=admin,
    )
    assert isolated_repository.resolve_field_acceptance_token(token) is not None
    isolated_repository.revoke_field_acceptance_credential(summary.id, acting_user=admin)
    assert isolated_repository.resolve_field_acceptance_token(token) is None
    # Idempotent: revoking an already-revoked credential does not raise.
    revoked_again = isolated_repository.revoke_field_acceptance_credential(summary.id, acting_user=admin)
    assert revoked_again.revoked_at is not None


def test_revoking_an_unknown_credential_id_raises(isolated_repository: ProductRepository) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    with pytest.raises(ValueError, match="field_acceptance_credential_not_found"):
        isolated_repository.revoke_field_acceptance_credential("does-not-exist", acting_user=admin)


def test_resolve_field_acceptance_token_returns_none_once_expired(
    isolated_repository: ProductRepository,
) -> None:
    """A server restart must not accidentally resurrect a revoked *or*
    expired credential -- `resolve_field_acceptance_token` re-reads
    `expires_at` fresh from the row on every call, with no in-memory cache
    to survive or bypass. Constructs an already-expired row directly
    (mirroring `tests/test_local_identity_multi_user.py`'s own pattern of
    inserting fixture rows straight through the repository's session
    factory) rather than sleeping in a test."""

    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    token = generate_session_token()
    now = datetime.now(UTC)
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                FieldAcceptanceCredentialModel(
                    id="field-acceptance-expired-fixture",
                    label="Already Expired",
                    token_hash=hash_session_token(token),
                    created_at=now - timedelta(hours=2),
                    created_by_user_id=admin.id,
                    created_by_display_name=admin.display_name,
                    expires_at=now - timedelta(minutes=1),
                    revoked_at=None,
                    last_used_at=None,
                )
            )
    assert isolated_repository.resolve_field_acceptance_token(token) is None


# --- Authorization boundary over real HTTP ----------------------------------


async def test_missing_credential_on_a_protected_endpoint_is_401_not_anonymous(
    admin_client: httpx.AsyncClient,
) -> None:
    """Regression guard: no anonymous fallback exists anywhere in this
    mechanism (governing contract §15 "No bypass semantics")."""

    unauthenticated = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=unauthenticated, base_url="http://testserver") as anon_client:
        assert (await anon_client.get("/api/streams")).status_code == 401
        assert (await anon_client.get("/api/visits")).status_code == 401
        assert (
            await anon_client.post("/api/streams/stream-backyard-feeder/observation/start")
        ).status_code == 401
        assert (
            await anon_client.post("/api/streams/stream-backyard-feeder/observation/stop")
        ).status_code == 401


async def test_malformed_or_unknown_bearer_token_is_401(admin_client: httpx.AsyncClient) -> None:
    for header_value in ("Bearer not-a-real-token", "Bearer ", "NotBearer sometoken", ""):
        transport = httpx.ASGITransport(app=app)
        headers = {"Authorization": header_value} if header_value else {}
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers=headers) as client:
            response = await client.get("/api/streams")
            assert response.status_code == 401, f"{header_value!r} must not authenticate"


async def test_valid_field_acceptance_token_satisfies_authenticated_tier_reads(
    admin_client: httpx.AsyncClient,
) -> None:
    created = await create_credential(admin_client)
    async with await bearer_client(created["token"]) as client:
        streams = await client.get("/api/streams")
        assert streams.status_code == 200
        visits = await client.get("/api/visits")
        assert visits.status_code == 200
        counterfactual = await client.get(
            "/api/streams/stream-backyard-feeder/observation/counterfactual",
            params={"start_offset_ms": 0, "end_offset_ms": 1000},
        )
        assert counterfactual.status_code == 200
        status = await client.get("/api/streams/stream-backyard-feeder/observation/status")
        assert status.status_code == 200


async def test_valid_field_acceptance_token_can_start_and_stop_real_observation(
    admin_client: httpx.AsyncClient,
) -> None:
    """The one narrow otherwise-Administrator-tier action this credential
    is allowed to perform, proven against the real handler (not merely the
    authorization gate) -- the auto-seeded demo `stream-backyard-feeder`
    configured onto the RTSP/live-monitoring lane, the same fixture shape
    `tests/test_observation_unified_api.py` already establishes."""

    configured = await admin_client.patch(
        "/api/sources/source-backyard-demo/provider-configuration",
        json={"provider_key": "external_url", "config": {"live_stream_url": "rtsp://camera.local/live", "live_stream_type": "rtsp"}},
    )
    assert configured.status_code == 200, configured.text

    created = await create_credential(admin_client)
    async with await bearer_client(created["token"]) as client:
        start = await client.post("/api/streams/stream-backyard-feeder/observation/start")
        assert start.status_code == 200, start.text
        stop = await client.post("/api/streams/stream-backyard-feeder/observation/stop")
        assert stop.status_code == 200, stop.text

    audit = await admin_client.get("/api/admin/audit-log")
    actions = {(entry["action"], entry["actor_display_name"]) for entry in audit.json()}
    assert any(
        action == "stream.observation_started" and actor is not None and "Field Acceptance Operator" in actor
        for action, actor in actions
    )
    assert any(
        action == "stream.observation_stopped" and actor is not None and "Field Acceptance Operator" in actor
        for action, actor in actions
    )
    # A field-acceptance principal is never a `UserModel` row.
    started_entry = next(e for e in audit.json() if e["action"] == "stream.observation_started")
    assert started_entry["actor_user_id"] is None


async def test_field_acceptance_token_cannot_perform_unrelated_administrator_actions(
    admin_client: httpx.AsyncClient,
) -> None:
    created = await create_credential(admin_client)
    async with await bearer_client(created["token"]) as client:
        assert (await client.post("/api/sources", json={"name": "New Camera"})).status_code == 403
        assert (
            await client.patch("/api/admin/installation-settings", json={"installation_name": "Hijacked"})
        ).status_code == 403
        assert (
            await client.post(
                "/api/admin/users",
                json={"display_name": "Eve", "login_identity": "eve", "password": "whatever12345", "role": "administrator"},
            )
        ).status_code == 403
        assert (await client.get("/api/admin/users")).status_code == 403
        assert (await client.get("/api/admin/audit-log")).status_code == 403
        assert (
            await client.post(
                "/api/admin/field-acceptance-credentials", json={"label": "self-escalation", "expires_in_hours": 24}
            )
        ).status_code == 403, "a field-acceptance credential must not be able to mint another one"
        assert (
            await client.post("/api/settings/backups")
        ).status_code == 403
        assert (
            await client.post("/api/zones", json={"stream_id": "stream-backyard-feeder", "name": "x", "zone_type": "privacy", "polygon": []})
        ).status_code == 403
        # Other operational capture controls stay out of this credential's
        # deliberately narrow scope -- only Observation start/stop is
        # allowlisted, not every "arm a pipeline" action.
        assert (await client.post("/api/streams/stream-backyard-feeder/monitor/start")).status_code == 403
        assert (await client.post("/api/streams/stream-backyard-feeder/live-motion/start")).status_code == 403


async def test_field_acceptance_token_cannot_perform_reviewer_actions(admin_client: httpx.AsyncClient) -> None:
    created = await create_credential(admin_client)
    async with await bearer_client(created["token"]) as client:
        response = await client.post(
            "/api/review-labels", json={"target_type": "visit", "target_id": "does-not-matter", "label": "x"}
        )
        assert response.status_code == 403


async def test_revoked_field_acceptance_token_fails_on_its_very_next_use(
    admin_client: httpx.AsyncClient,
) -> None:
    created = await create_credential(admin_client)
    async with await bearer_client(created["token"]) as client:
        first = await client.get("/api/streams")
        assert first.status_code == 200

    revoke = await admin_client.post(f"/api/admin/field-acceptance-credentials/{created['id']}/revoke")
    assert revoke.status_code == 200
    assert revoke.json()["revoked_at"] is not None

    async with await bearer_client(created["token"]) as client:
        second = await client.get("/api/streams")
        assert second.status_code == 401
        start_attempt = await client.post("/api/streams/stream-backyard-feeder/observation/start")
        assert start_attempt.status_code == 401


async def test_expired_field_acceptance_token_is_rejected_over_http(
    admin_client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    admin_user_id = (await admin_client.get("/api/auth/session")).json()["id"]
    token = generate_session_token()
    now = datetime.now(UTC)
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                FieldAcceptanceCredentialModel(
                    id="field-acceptance-expired-http-fixture",
                    label="Already Expired",
                    token_hash=hash_session_token(token),
                    created_at=now - timedelta(hours=2),
                    created_by_user_id=admin_user_id,
                    created_by_display_name="Ada Admin",
                    expires_at=now - timedelta(minutes=1),
                    revoked_at=None,
                    last_used_at=None,
                )
            )
    async with await bearer_client(token) as client:
        response = await client.get("/api/streams")
        assert response.status_code == 401


async def test_a_signed_in_viewer_cookie_cannot_combine_with_a_bearer_token_to_escalate(
    admin_client: httpx.AsyncClient,
) -> None:
    """A request carrying both a low-privilege human session cookie and a
    valid field-acceptance bearer token must be judged on whichever
    identity actually satisfies the tier -- never let the two combine into
    more privilege than either grants alone."""

    viewer_created = await admin_client.post(
        "/api/admin/users",
        json={"display_name": "Vic Viewer", "login_identity": "vic", "password": "viewer-password-1", "role": "viewer"},
    )
    assert viewer_created.status_code == 201
    created = await create_credential(admin_client)

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", headers={"Authorization": f"Bearer {created['token']}"}
    ) as client:
        signed_in = await client.post(
            "/api/auth/sign-in", json={"login_identity": "vic", "password": "viewer-password-1"}
        )
        assert signed_in.status_code == 200
        # Viewer cookie + valid field-acceptance bearer token together:
        # still no camera/source administration.
        response = await client.post("/api/sources", json={"name": "New Camera"})
        assert response.status_code == 403


async def test_no_debug_header_or_localhost_exemption_bypasses_authentication(
    admin_client: httpx.AsyncClient,
) -> None:
    """Regression guard against exactly the bypass shapes the governing
    contract explicitly forbids: a special request header, or treating
    `127.0.0.1`/localhost as itself a trust boundary."""

    transport = httpx.ASGITransport(app=app)
    bogus_headers = {
        "X-Debug-Bypass": "true",
        "X-Forwarded-For": "127.0.0.1",
        "X-Real-Ip": "127.0.0.1",
        "X-Admin": "true",
        "X-Mockingbird-Trusted": "true",
    }
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", headers=bogus_headers) as client:
        assert (await client.get("/api/streams")).status_code == 401
        assert (
            await client.post("/api/streams/stream-backyard-feeder/observation/start")
        ).status_code == 401


async def test_field_acceptance_endpoints_are_reachable_only_through_the_real_authorization_gate(
    admin_client: httpx.AsyncClient,
) -> None:
    """No parallel/insecure auth stack: the credential this milestone adds
    is checked by the exact same central `install_authorization` middleware
    every other request already passes through -- an out-of-role human
    Administrator action (create) still needs the real cookie session, a
    query-string token is never accepted, and a token is never read from
    anywhere but the `Authorization` header."""

    created = await create_credential(admin_client)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Token in the query string must not authenticate.
        response = await client.get("/api/streams", params={"token": created["token"]})
        assert response.status_code == 401

    # Token as a cookie value must not authenticate (only a real
    # `mb_session` cookie, or a real `Authorization: Bearer` header).
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver", cookies={"mb_session": created["token"]}
    ) as cookie_client:
        response = await cookie_client.get("/api/streams")
        assert response.status_code == 401
