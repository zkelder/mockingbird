"""Local Identity, Multi-User & Organization Access v1 (see
docs/local-identity-multi-user-contract.md).

Covers: password hashing; first-run administrator bootstrap (race-safety,
replay-proofing, no default credentials); sign-in/session lifecycle
(disable/enable and role changes taking effect immediately, self-service
password change preserving the acting session while revoking others,
admin password reset revoking everything); server-side authorization for
Viewer/Reviewer/Administrator tiers over real HTTP; review attribution
(`reviewed_by_user_id` set from the real signed-in actor, `review_origin`/
`reviewer_identity` never force-overridden); the pre-existing
`expected_state_token` optimistic-concurrency mechanism newly reused by
`POST /api/review-labels` and, per-item, by `POST /api/review-queue/
bulk-correct` (a stale item in a batch is rejected on its own -- a
`failed` result carrying the same conflict message as the single-item
409 -- without blocking or silently overwriting any other item in that
same batch); the audit trail (material actions recorded, no secrets in
metadata); and backup/restore identity semantics (users/roles/audit
history survive a restore; a legacy row with no signed-in-user
attribution stays honestly unattributed rather than having one invented).

`mockingbird.api.auth` enforces the real Viewer/Reviewer/Administrator
policy on every request, unconditionally -- HTTP-level tests here exercise
that real enforcement path directly (real bootstrap, real sign-in, real
session cookies), unlike the ~100 pre-existing test files elsewhere that
predate this milestone and get an authenticated session from
`tests.conftest.LegacyAuthenticatedTestClient` instead. See
`mockingbird.api.auth`'s own module docstring for the full rationale.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    AdministratorBootstrapRequest,
    AdminPasswordResetRequest,
    InstallationSettingsUpdate,
    ReviewCorrectionCreate,
    SelfPasswordChangeRequest,
    SignInRequest,
    UserCreate,
    UserEnabledUpdate,
    UserRole,
    UserRoleUpdate,
)
from mockingbird.repository.product_repository import ProductRepository, ReviewRevisionConflictError
from mockingbird.security.passwords import (
    WeakPasswordError,
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from mockingbird.storage.models import (
    CameraNodePendingSetupModel,
    CameraSourceModel,
    EventModel,
    ReviewLabelModel,
    VisitModel,
)

pytestmark = pytest.mark.anyio

STREAM_ID = "stream-backyard-feeder"
VISIT_ID = "visit-local-identity-fixture"
EVENT_ID = "event-local-identity-fixture"


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


def add_reviewable_visit(
    repository: ProductRepository, *, visit_id: str = VISIT_ID, event_id: str = EVENT_ID
) -> None:
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=STREAM_ID,
                    title="Local identity fixture",
                    event_type="local_identity_fixture",
                    started_at=now,
                    ended_at=now,
                    primary_zone_id="zone-feeder",
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="bird",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                    zone_id="zone-feeder",
                    is_superseded=False,
                )
            )


# --- Password hashing (Tier 1, pure/no DB) ----------------------------------


def test_password_hash_roundtrip_and_wrong_password_rejected() -> None:
    stored = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", stored) is True
    assert verify_password("wrong password entirely", stored) is False
    # Never plaintext, never reversible-looking.
    assert "correct horse" not in stored


def test_password_hash_is_self_describing_and_salted() -> None:
    first = hash_password("same password twice")
    second = hash_password("same password twice")
    assert first != second, "two hashes of the same password must use different random salts"
    assert first.startswith("scrypt$")
    assert verify_password("same password twice", first)
    assert verify_password("same password twice", second)


def test_verify_password_fails_closed_on_malformed_stored_hash() -> None:
    assert verify_password("anything", "not-a-real-hash") is False
    assert verify_password("anything", "scrypt$garbled$$") is False
    assert needs_rehash("not-a-real-hash") is True


def test_validate_password_strength_rejects_short_and_absurdly_long() -> None:
    with pytest.raises(WeakPasswordError):
        validate_password_strength("short1")
    with pytest.raises(WeakPasswordError):
        validate_password_strength("x" * 300)
    validate_password_strength("a reasonably long password")  # must not raise


# --- First-run administrator bootstrap ---------------------------------------


def test_bootstrap_creates_administrator_and_signs_in(isolated_repository: ProductRepository) -> None:
    assert isolated_repository.has_eligible_administrator() is False
    current_user, token = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="Ada", password="correct horse battery")
    )
    assert current_user.role == UserRole.administrator
    assert current_user.login_identity == "ada", "login_identity is stored lowercase-normalized"
    assert isolated_repository.has_eligible_administrator() is True
    resolved = isolated_repository.resolve_session(token)
    assert resolved is not None and resolved.id == current_user.id


def test_bootstrap_cannot_be_replayed_once_an_administrator_exists(
    isolated_repository: ProductRepository,
) -> None:
    isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    with pytest.raises(ValueError, match="administrator_already_exists"):
        isolated_repository.create_first_administrator(
            AdministratorBootstrapRequest(display_name="Eve Evil", login_identity="eve", password="whatever12345")
        )


def test_bootstrap_rejects_a_weak_password(isolated_repository: ProductRepository) -> None:
    with pytest.raises(WeakPasswordError):
        isolated_repository.create_first_administrator(
            AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="short")
        )
    assert isolated_repository.has_eligible_administrator() is False


def test_no_default_administrator_or_default_credentials(isolated_repository: ProductRepository) -> None:
    """A fresh repository must start with zero users and no way to sign
    in -- no hidden `admin`/`admin`, no seeded account of any kind."""

    assert isolated_repository.list_users() == []
    assert isolated_repository.authenticate_user(SignInRequest(login_identity="admin", password="admin")) is None


async def test_bootstrap_over_http_sets_a_working_session_cookie(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/setup/administrator",
        json={"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"},
    )
    assert response.status_code == 201, response.text
    assert "mb_session" in response.cookies
    session_response = await client.get("/api/auth/session")
    assert session_response.status_code == 200
    assert session_response.json()["role"] == "administrator"

    replay = await client.post(
        "/api/setup/administrator",
        json={"display_name": "Eve", "login_identity": "eve", "password": "whatever12345"},
    )
    assert replay.status_code == 409, replay.text


# --- Sign-in / session lifecycle ---------------------------------------------


def test_sign_in_rejects_unknown_user_wrong_password_and_disabled_user(
    isolated_repository: ProductRepository,
) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    assert isolated_repository.authenticate_user(SignInRequest(login_identity="nobody", password="x" * 12)) is None
    assert isolated_repository.authenticate_user(SignInRequest(login_identity="ada", password="wrong password")) is None

    viewer = isolated_repository.create_user(
        UserCreate(display_name="Vic Viewer", login_identity="vic", password="viewer-password-1", role=UserRole.viewer),
        acting_user=admin,
    )
    isolated_repository.set_user_enabled(viewer.id, UserEnabledUpdate(enabled=False), acting_user=admin)
    assert isolated_repository.authenticate_user(SignInRequest(login_identity="vic", password="viewer-password-1")) is None


def test_disabling_a_user_revokes_access_on_the_very_next_request(
    isolated_repository: ProductRepository,
) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    reviewer = isolated_repository.create_user(
        UserCreate(display_name="Rae Reviewer", login_identity="rae", password="reviewer-password-1", role=UserRole.reviewer),
        acting_user=admin,
    )
    _, token = isolated_repository.authenticate_user(
        SignInRequest(login_identity="rae", password="reviewer-password-1")
    )
    assert isolated_repository.resolve_session(token) is not None

    isolated_repository.set_user_enabled(reviewer.id, UserEnabledUpdate(enabled=False), acting_user=admin)
    assert isolated_repository.resolve_session(token) is None, (
        "a disabled user's existing session must stop resolving immediately -- "
        "no separate revocation sweep should be required"
    )

    isolated_repository.set_user_enabled(reviewer.id, UserEnabledUpdate(enabled=True), acting_user=admin)
    assert isolated_repository.resolve_session(token) is not None


def test_role_change_takes_effect_immediately_without_a_new_identity(
    isolated_repository: ProductRepository,
) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    viewer = isolated_repository.create_user(
        UserCreate(display_name="Vic Viewer", login_identity="vic", password="viewer-password-1", role=UserRole.viewer),
        acting_user=admin,
    )
    _, token = isolated_repository.authenticate_user(SignInRequest(login_identity="vic", password="viewer-password-1"))
    assert isolated_repository.resolve_session(token).role == UserRole.viewer

    isolated_repository.update_user_role(viewer.id, UserRoleUpdate(role=UserRole.reviewer), acting_user=admin)
    resolved = isolated_repository.resolve_session(token)
    assert resolved is not None
    assert resolved.id == viewer.id, "still the same identity, not a new account"
    assert resolved.role == UserRole.reviewer, "the role change is visible on the very next resolution"


def test_last_enabled_administrator_cannot_be_demoted_or_disabled(
    isolated_repository: ProductRepository,
) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    with pytest.raises(ValueError, match="cannot_remove_last_administrator"):
        isolated_repository.update_user_role(admin.id, UserRoleUpdate(role=UserRole.viewer), acting_user=admin)
    with pytest.raises(ValueError, match="cannot_disable_last_administrator"):
        isolated_repository.set_user_enabled(admin.id, UserEnabledUpdate(enabled=False), acting_user=admin)

    # A second enabled Administrator removes the constraint.
    other = isolated_repository.create_user(
        UserCreate(display_name="Bea Backup", login_identity="bea", password="backup-admin-pw1", role=UserRole.administrator),
        acting_user=admin,
    )
    isolated_repository.update_user_role(admin.id, UserRoleUpdate(role=UserRole.viewer), acting_user=other)  # must not raise


def test_self_password_change_preserves_current_session_revokes_others(
    isolated_repository: ProductRepository,
) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    reviewer = isolated_repository.create_user(
        UserCreate(display_name="Rae Reviewer", login_identity="rae", password="reviewer-password-1", role=UserRole.reviewer),
        acting_user=admin,
    )
    _, token_a = isolated_repository.authenticate_user(SignInRequest(login_identity="rae", password="reviewer-password-1"))
    _, token_b = isolated_repository.authenticate_user(SignInRequest(login_identity="rae", password="reviewer-password-1"))

    isolated_repository.change_own_password(
        reviewer.id,
        SelfPasswordChangeRequest(current_password="reviewer-password-1", new_password="a-brand-new-password-2"),
        current_session_token=token_a,
    )
    assert isolated_repository.resolve_session(token_a) is not None, "the session making the request survives"
    assert isolated_repository.resolve_session(token_b) is None, "every other session is revoked"


def test_self_password_change_requires_the_correct_current_password(
    isolated_repository: ProductRepository,
) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    with pytest.raises(ValueError, match="current_password_incorrect"):
        isolated_repository.change_own_password(
            admin.id, SelfPasswordChangeRequest(current_password="totally wrong", new_password="a-brand-new-password-2")
        )


def test_admin_reset_password_revokes_every_existing_session(
    isolated_repository: ProductRepository,
) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    reviewer = isolated_repository.create_user(
        UserCreate(display_name="Rae Reviewer", login_identity="rae", password="reviewer-password-1", role=UserRole.reviewer),
        acting_user=admin,
    )
    _, token = isolated_repository.authenticate_user(SignInRequest(login_identity="rae", password="reviewer-password-1"))
    isolated_repository.admin_reset_password(reviewer.id, AdminPasswordResetRequest(new_password="admin-set-password-2"), acting_user=admin)
    assert isolated_repository.resolve_session(token) is None
    assert isolated_repository.authenticate_user(SignInRequest(login_identity="rae", password="admin-set-password-2")) is not None


def test_sign_out_revokes_exactly_that_session(isolated_repository: ProductRepository) -> None:
    _, token = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    isolated_repository.revoke_session(token)
    assert isolated_repository.resolve_session(token) is None
    # Idempotent: revoking again (or an unknown token) must not raise.
    isolated_repository.revoke_session(token)
    isolated_repository.revoke_session("not-a-real-token")


# --- Server-side authorization over real HTTP --------------------------------


async def test_unauthenticated_request_is_rejected_server_side(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/streams")
    assert response.status_code == 401
    assert "detail" in response.json()


async def test_setup_and_public_endpoints_remain_reachable_unauthenticated(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/setup/state")).status_code == 200
    assert (await client.get("/api/settings/installation")).status_code == 200
    assert (await client.get("/health")).status_code == 200


async def test_viewer_can_read_but_cannot_review_or_administer(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/setup/administrator",
        json={"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"},
    )
    created = await client.post(
        "/api/admin/users",
        json={"display_name": "Vic Viewer", "login_identity": "vic", "password": "viewer-password-1", "role": "viewer"},
    )
    assert created.status_code == 201, created.text

    viewer_client_transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=viewer_client_transport, base_url="http://testserver") as viewer_client:
        signed_in = await viewer_client.post(
            "/api/auth/sign-in", json={"login_identity": "vic", "password": "viewer-password-1"}
        )
        assert signed_in.status_code == 200

        readable = await viewer_client.get("/api/streams")
        assert readable.status_code == 200, "Viewer can read Viewer-safe data"

        review_attempt = await viewer_client.post(
            "/api/review-labels",
            json={"target_type": "visit", "target_id": "does-not-matter", "label": "x"},
        )
        assert review_attempt.status_code == 403

        admin_attempt = await viewer_client.post(
            "/api/sources", json={"name": "New Camera"}
        )
        assert admin_attempt.status_code == 403

        users_attempt = await viewer_client.get("/api/admin/users")
        assert users_attempt.status_code == 403


async def test_reviewer_can_review_but_cannot_administer(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/setup/administrator",
        json={"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"},
    )
    await client.post(
        "/api/admin/users",
        json={"display_name": "Rae Reviewer", "login_identity": "rae", "password": "reviewer-password-1", "role": "reviewer"},
    )

    reviewer_transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=reviewer_transport, base_url="http://testserver") as reviewer_client:
        signed_in = await reviewer_client.post(
            "/api/auth/sign-in", json={"login_identity": "rae", "password": "reviewer-password-1"}
        )
        assert signed_in.status_code == 200

        admin_attempt = await reviewer_client.patch(
            "/api/admin/installation-settings", json={"installation_name": "Hijacked"}
        )
        assert admin_attempt.status_code in (403, 405)  # PUT is the real method; either way, never 200.

        put_attempt = await reviewer_client.put(
            "/api/admin/installation-settings", json={"installation_name": "Hijacked"}
        )
        assert put_attempt.status_code == 403


async def test_disabling_a_user_mid_session_blocks_further_requests_over_http(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    await client.post(
        "/api/setup/administrator",
        json={"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"},
    )
    await client.post(
        "/api/admin/users",
        json={"display_name": "Rae Reviewer", "login_identity": "rae", "password": "reviewer-password-1", "role": "reviewer"},
    )
    reviewer_transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=reviewer_transport, base_url="http://testserver") as reviewer_client:
        await reviewer_client.post(
            "/api/auth/sign-in", json={"login_identity": "rae", "password": "reviewer-password-1"}
        )
        assert (await reviewer_client.get("/api/streams")).status_code == 200

        users = (await client.get("/api/admin/users")).json()
        rae = next(user for user in users if user["login_identity"] == "rae")
        disabled = await client.patch(
            f"/api/admin/users/{rae['id']}/enabled", json={"enabled": False}
        )
        assert disabled.status_code == 200

        assert (await reviewer_client.get("/api/streams")).status_code == 401


async def test_sign_out_over_http_ends_the_session(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/setup/administrator",
        json={"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"},
    )
    assert (await client.get("/api/streams")).status_code == 200
    signed_out = await client.post("/api/auth/sign-out")
    assert signed_out.status_code == 204
    assert (await client.get("/api/streams")).status_code == 401


# --- Review attribution -------------------------------------------------


async def test_review_correction_is_attributed_to_the_real_signed_in_reviewer(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    add_reviewable_visit(isolated_repository)
    await client.post(
        "/api/setup/administrator",
        json={"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"},
    )
    await client.post(
        "/api/admin/users",
        json={"display_name": "Rae Reviewer", "login_identity": "rae", "password": "reviewer-password-1", "role": "reviewer"},
    )
    reviewer_transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=reviewer_transport, base_url="http://testserver") as reviewer_client:
        signed_in = await reviewer_client.post(
            "/api/auth/sign-in", json={"login_identity": "rae", "password": "reviewer-password-1"}
        )
        reviewer_id = signed_in.json()["id"]

        correction = await reviewer_client.post(
            "/api/review-labels",
            json={"target_type": "visit", "target_id": VISIT_ID, "label": "American Robin", "review_origin": "human"},
        )
        assert correction.status_code == 201, correction.text
        review_label = correction.json()["review_label"]
        assert review_label["reviewed_by_user_id"] == reviewer_id
        assert review_label["reviewer_identity"] == "Rae Reviewer"
        assert review_label["review_origin"] == "human"
        assert review_label["is_authoritative"] is True


def test_non_human_origin_and_explicit_reviewer_identity_are_never_overridden(
    isolated_repository: ProductRepository,
) -> None:
    """A signed-in acting_user must never force `review_origin`/
    `reviewer_identity` -- only `reviewed_by_user_id` is unconditional.
    This is what keeps every pre-existing `agent_diagnostic`/
    `imported_curated` provenance test (which predates user identity)
    completely unaffected by this milestone."""

    add_reviewable_visit(isolated_repository)
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    result = isolated_repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=VISIT_ID, label="Blue Jay",
            review_origin="agent_diagnostic", reviewer_identity="claude-agent-test",
        ),
        acting_user=admin,
    )
    assert result.review_label.review_origin == "agent_diagnostic"
    assert result.review_label.reviewer_identity == "claude-agent-test"
    assert result.review_label.reviewed_by_user_id == admin.id, "the durable actor reference is still set"

    with isolated_repository.session_factory() as session:
        visit = session.get(VisitModel, VISIT_ID)
        assert visit.review_status == "needs_review", "a non-authoritative origin must never establish truth"


def test_offline_caller_with_no_acting_user_is_completely_unaffected(
    isolated_repository: ProductRepository,
) -> None:
    """The default parameter (`acting_user=None`) preserves the exact
    pre-existing behavior for every offline/CLI/demo-seed caller -- the
    entire population this milestone must not disturb."""

    add_reviewable_visit(isolated_repository)
    result = isolated_repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=VISIT_ID, label="House Finch", review_origin="human")
    )
    assert result.review_label.reviewed_by_user_id is None
    assert result.review_label.reviewer_identity is None


# --- Optimistic concurrency (Journey 5) --------------------------------------


def test_initial_correction_rejects_a_stale_expected_state_token(
    isolated_repository: ProductRepository,
) -> None:
    add_reviewable_visit(isolated_repository)
    with pytest.raises(ReviewRevisionConflictError, match="stale_reviewed_visit"):
        isolated_repository.create_review_label(
            ReviewCorrectionCreate(
                target_type="visit", target_id=VISIT_ID, label="American Robin",
                expected_state_token="0" * 24,
            )
        )


def test_initial_correction_succeeds_with_a_matching_expected_state_token(
    isolated_repository: ProductRepository,
) -> None:
    add_reviewable_visit(isolated_repository)
    with isolated_repository.session_factory() as session:
        current_token = isolated_repository._review_state_token(session, "visit", VISIT_ID)
    result = isolated_repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=VISIT_ID, label="American Robin", expected_state_token=current_token,
        )
    )
    assert result.review_label.label


async def test_two_reviewers_stale_write_is_rejected_not_silently_overwritten(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    """Journey 5: Alice opens a Visit; Bob corrects it first; Alice submits
    against what she originally saw. Bob's newer truth must remain
    authoritative -- Alice gets a structured conflict, not a silent
    overwrite."""

    add_reviewable_visit(isolated_repository)
    await client.post(
        "/api/setup/administrator",
        json={"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"},
    )
    for name, identity in (("Alice Reviewer", "alice"), ("Bob Reviewer", "bob")):
        await client.post(
            "/api/admin/users",
            json={"display_name": name, "login_identity": identity, "password": f"{identity}-password-1", "role": "reviewer"},
        )

    async def sign_in(login_identity: str) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app)
        session = httpx.AsyncClient(transport=transport, base_url="http://testserver")
        await session.post(
            "/api/auth/sign-in", json={"login_identity": login_identity, "password": f"{login_identity}-password-1"}
        )
        return session

    alice = await sign_in("alice")
    bob = await sign_in("bob")

    alice_view = await alice.get(f"/api/visits/{VISIT_ID}/detail")
    stale_token = alice_view.json()["review_state_token"]

    bob_correction = await bob.post(
        "/api/review-labels",
        json={"target_type": "visit", "target_id": VISIT_ID, "label": "bobs_robin", "review_origin": "human", "expected_state_token": stale_token},
    )
    assert bob_correction.status_code == 201, bob_correction.text

    alice_correction = await alice.post(
        "/api/review-labels",
        json={"target_type": "visit", "target_id": VISIT_ID, "label": "alices_cardinal", "review_origin": "human", "expected_state_token": stale_token},
    )
    assert alice_correction.status_code == 409, alice_correction.text

    with isolated_repository.session_factory() as session:
        visit = session.get(VisitModel, VISIT_ID)
        assert visit.reviewed_label == "bobs_robin", "Bob's newer truth remains authoritative"

    await alice.aclose()
    await bob.aclose()


OTHER_VISIT_ID = "visit-local-identity-fixture-bulk-2"
OTHER_EVENT_ID = "event-local-identity-fixture-bulk-2"


async def test_two_reviewers_bulk_correction_stale_write_is_rejected_not_silently_overwritten(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    """Bulk-correct counterpart to Journey 5 above -- with one deliberate
    difference from that single-item test's scenario, forced by this
    endpoint's own pre-existing design: `bulk_correct_review_queue_items`
    already refuses to touch anything that isn't still `needs_review` (see
    `_review_queue_bulk_correction_skip_reason`), so two SEQUENTIAL
    *authoritative* bulk corrections of the exact same Visit can never
    reach this test's new `expected_state_tokens` check at all -- Bob's
    first (authoritative) write already flips the Visit to `reviewed`,
    which makes Alice's second attempt bounce off that pre-existing
    eligibility rule as `skipped`, before her stale token is ever
    consulted. That pre-existing rule is *not* what this milestone closes.

    What it closes is the gap that rule leaves open: `_review_state_token`
    also folds in Visit curation state (`_visit_curation_state` -- Zone,
    supersession, evidence linkage), which can change without the Visit
    ever leaving `needs_review`. Bob moves the Visit to a different Zone
    (represented here the same economical way `add_reviewable_visit`
    itself sets up fixtures -- a direct, minimal repository mutation,
    rather than standing up a second real Zone/Stream graph just to drive
    the full `/api/visits/{id}/zone` endpoint's own unrelated validation)
    while Alice is still holding the token from before that move; her
    subsequent authoritative bulk correction across two Visits must reject
    the stale one on its own -- via the *new* per-item token check, since
    the pre-existing eligibility rule alone would have let it through --
    while the second, still-fresh Visit succeeds in that same batch call:
    a stale item never blocks or silently overwrites the rest of the
    batch."""

    add_reviewable_visit(isolated_repository)
    add_reviewable_visit(isolated_repository, visit_id=OTHER_VISIT_ID, event_id=OTHER_EVENT_ID)
    await client.post(
        "/api/setup/administrator",
        json={"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"},
    )
    for name, identity in (("Alice Reviewer", "alice"), ("Bob Reviewer", "bob")):
        await client.post(
            "/api/admin/users",
            json={"display_name": name, "login_identity": identity, "password": f"{identity}-password-1", "role": "reviewer"},
        )

    async def sign_in(login_identity: str) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app)
        session = httpx.AsyncClient(transport=transport, base_url="http://testserver")
        await session.post(
            "/api/auth/sign-in", json={"login_identity": login_identity, "password": f"{login_identity}-password-1"}
        )
        return session

    alice = await sign_in("alice")

    stale_token = (await alice.get(f"/api/visits/{VISIT_ID}/detail")).json()["review_state_token"]
    fresh_token = (await alice.get(f"/api/visits/{OTHER_VISIT_ID}/detail")).json()["review_state_token"]

    # Bob reassigns the Visit's Zone -- a real Reviewer-tier curation
    # action (`POST /api/visits/{visit_id}/zone`); done here as a direct
    # mutation for fixture economy, but its effect on `_visit_curation_
    # state` is identical either way. `review_status` is untouched (still
    # `needs_review`, still bulk-correction-eligible), yet the review-state
    # token has already moved past what Alice is still holding.
    with isolated_repository.session_factory() as session:
        with session.begin():
            moved_visit = session.get(VisitModel, VISIT_ID)
            moved_visit.zone_id = "zone-a-different-one"
    with isolated_repository.session_factory() as session:
        assert session.get(VisitModel, VISIT_ID).review_status == "needs_review", (
            "a Zone reassignment must never itself establish reviewed truth"
        )

    alice_correction = await alice.post(
        "/api/review-queue/bulk-correct",
        json={
            "target_type": "visit",
            "target_ids": [VISIT_ID, OTHER_VISIT_ID],
            "label": "alices_cardinal",
            "review_origin": "human",
            # Alice's tokens reflect what she saw before Bob's note --
            # `VISIT_ID` is now stale; `OTHER_VISIT_ID` is still fresh.
            "expected_state_tokens": {VISIT_ID: stale_token, OTHER_VISIT_ID: fresh_token},
        },
    )
    assert alice_correction.status_code == 200, alice_correction.text
    body = alice_correction.json()
    assert body["requested_count"] == 2
    assert body["succeeded_count"] == 1
    assert body["failed_count"] == 1
    results_by_target = {result["target_id"]: result for result in body["results"]}
    assert results_by_target[VISIT_ID]["status"] == "failed"
    assert results_by_target[VISIT_ID]["message"] == "This item changed. Refresh it before saving a correction."
    assert results_by_target[OTHER_VISIT_ID]["status"] == "succeeded"

    with isolated_repository.session_factory() as session:
        stale_visit = session.get(VisitModel, VISIT_ID)
        assert stale_visit.review_status == "needs_review", (
            "Alice's stale correction must never silently establish reviewed truth"
        )
        assert stale_visit.reviewed_label is None
        fresh_visit = session.get(VisitModel, OTHER_VISIT_ID)
        assert fresh_visit.reviewed_label == "alices_cardinal", (
            "the non-conflicting item in the same batch still succeeds -- a stale "
            "item is rejected per-item, never a whole-batch abort"
        )

    await alice.aclose()


# --- Audit trail --------------------------------------------------------


async def test_audit_trail_records_material_actions_with_no_secrets(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/setup/administrator",
        json={"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"},
    )
    await client.post(
        "/api/admin/users",
        json={"display_name": "Rae Reviewer", "login_identity": "rae", "password": "super-secret-password-1", "role": "reviewer"},
    )
    users = (await client.get("/api/admin/users")).json()
    rae = next(user for user in users if user["login_identity"] == "rae")
    await client.patch(f"/api/admin/users/{rae['id']}/role", json={"role": "administrator"})

    audit = await client.get("/api/admin/audit-log")
    assert audit.status_code == 200
    entries = audit.json()
    actions = {entry["action"] for entry in entries}
    assert "user.bootstrap_administrator" in actions
    assert "user.created" in actions
    assert "user.role_changed" in actions

    import json as json_module

    for entry in entries:
        assert entry["actor_display_name"] is not None
        blob = json_module.dumps(entry).lower()
        assert "super-secret-password" not in blob
        assert "password_hash" not in blob
        assert "mb_session" not in blob


async def test_audit_log_is_administrator_only(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/setup/administrator",
        json={"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"},
    )
    await client.post(
        "/api/admin/users",
        json={"display_name": "Vic Viewer", "login_identity": "vic", "password": "viewer-password-1", "role": "viewer"},
    )
    viewer_transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=viewer_transport, base_url="http://testserver") as viewer_client:
        await viewer_client.post(
            "/api/auth/sign-in", json={"login_identity": "vic", "password": "viewer-password-1"}
        )
        response = await viewer_client.get("/api/admin/audit-log")
        assert response.status_code == 403


# --- Legacy / unattributed review history (Journey 11) -----------------------


def test_legacy_review_row_with_no_actor_stays_honestly_unattributed(
    isolated_repository: ProductRepository,
) -> None:
    """A row written before user identity existed (or by an offline/CLI
    pathway) must round-trip through the API exactly as `reviewed_by_
    user_id=None` -- never a fabricated actor."""

    add_reviewable_visit(isolated_repository)
    now = datetime.now(UTC)
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                ReviewLabelModel(
                    id="review-label-legacy-fixture",
                    target_type="visit",
                    target_id=VISIT_ID,
                    label="legacy_unattributed_species",
                    notes=None,
                    created_at=now,
                    review_origin="legacy_unattributed",
                    reviewer_identity=None,
                    reviewed_by_user_id=None,
                )
            )

    labels = isolated_repository.list_review_labels()
    legacy = next(label for label in labels if label.id == "review-label-legacy-fixture")
    assert legacy.reviewed_by_user_id is None
    assert legacy.reviewer_identity is None
    assert legacy.review_origin == "legacy_unattributed"


# --- Camera Node identity separation (Journey 8) -----------------------


def test_camera_node_credential_tables_have_no_relationship_to_users(
    isolated_repository: ProductRepository,
) -> None:
    """Device identity and human identity must be structurally independent
    -- not merely "we didn't happen to touch it." Confirms directly, at
    the schema level, that neither Camera Node credential table has any
    foreign key into `users` (so a human user row can never even be
    referenced by device-credential storage, let alone required by it)."""

    for model in (CameraSourceModel, CameraNodePendingSetupModel):
        for column in model.__table__.columns:
            for fk in column.foreign_keys:
                assert fk.column.table.name != "users", (
                    f"{model.__tablename__}.{column.name} must never reference users -- "
                    "device and human identity are separate systems"
                )


async def test_disabling_and_resetting_every_human_user_leaves_camera_node_pairing_untouched(
    isolated_repository: ProductRepository,
) -> None:
    """Journey 8, end to end: create a real Camera Node pending-setup
    credential (the actual device-identity record this product persists
    on a real pairing -- see CameraNodePendingSetupModel), then disable
    and password-reset every human user. The Camera Node record -- the
    thing real Camera Node hardware authenticates with -- must be
    completely unaffected, because nothing in this milestone's human-
    identity tables/logic ever touches it."""

    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password="correct horse battery")
    )
    reviewer = isolated_repository.create_user(
        UserCreate(display_name="Rae Reviewer", login_identity="rae", password="reviewer-password-1", role=UserRole.reviewer),
        acting_user=admin,
    )

    now = datetime.now(UTC)
    with isolated_repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraNodePendingSetupModel(
                    token="pairing-token-journey-8-fixture",
                    node_id="node-journey-8-fixture",
                    display_name="Backyard Camera Node",
                    api_version="v1",
                    base_address="http://192.0.2.10:8787",
                    credential="device-credential-never-a-human-password",
                    capability_fingerprint="fingerprint-journey-8-fixture",
                    cameras_json="[]",
                    status="active",
                    monitoring_enabled=False,
                    created_at=now,
                    updated_at=now,
                )
            )

    # Disable and reset both human accounts -- the most disruptive human-
    # identity actions this product offers short of a schema-level delete
    # (which this product does not expose at all -- disable is the answer).
    isolated_repository.set_user_enabled(reviewer.id, UserEnabledUpdate(enabled=False), acting_user=admin)
    isolated_repository.admin_reset_password(
        reviewer.id, AdminPasswordResetRequest(new_password="a-brand-new-password-2"), acting_user=admin
    )

    with isolated_repository.session_factory() as session:
        pending = session.get(CameraNodePendingSetupModel, "pairing-token-journey-8-fixture")
        assert pending is not None, "the Camera Node record must not have been touched or removed"
        assert pending.credential == "device-credential-never-a-human-password"
        assert pending.status == "active"


# --- Backup/restore identity semantics (Journey 10) ---------------------


async def test_backup_restore_preserves_users_roles_and_audit_history(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    """Exercises the real `POST /api/settings/backups` + `.../restore`
    product flow (not the storage library in isolation) -- matching how
    `tests/test_local_backup_recovery.py`'s own API-level tests already
    do it, since `LocalBackupManager.replace_live_files` restores in place
    over the currently-configured database/media paths, not into an
    arbitrary new location."""

    await client.post(
        "/api/setup/administrator",
        json={"display_name": "Ada Admin", "login_identity": "ada", "password": "correct horse battery"},
    )
    await client.post(
        "/api/admin/users",
        json={"display_name": "Rae Reviewer", "login_identity": "rae", "password": "reviewer-password-1", "role": "reviewer"},
    )
    await client.put(
        "/api/admin/installation-settings", json={"installation_name": "Test Yard"}
    )
    audit_before = len((await client.get("/api/admin/audit-log")).json())

    backup_response = await client.post("/api/settings/backups")
    assert backup_response.status_code == 201, backup_response.text
    backup_id = backup_response.json()["backup"]["id"]

    # A separate client: signing in on `client` itself would overwrite its
    # own admin session cookie with the reviewer's, and the restore below
    # needs to remain authenticated as the Administrator.
    reviewer_transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=reviewer_transport, base_url="http://testserver") as reviewer_client:
        reviewer_signed_in = await reviewer_client.post(
            "/api/auth/sign-in", json={"login_identity": "rae", "password": "reviewer-password-1"}
        )
    reviewer_signed_in_token = reviewer_signed_in.cookies.get("mb_session")
    assert reviewer_signed_in_token

    restore_response = await client.post(
        f"/api/settings/backups/{backup_id}/restore", json={"confirm": True}
    )
    assert restore_response.status_code == 200, restore_response.text

    # `restore_local_backup` swaps the process-wide repository singleton
    # (`configure_repository`) -- re-fetch it to inspect the now-active,
    # restored database directly.
    from mockingbird.api.main import get_repository

    restored_repository = get_repository()
    restored_users = {user.login_identity: user for user in restored_repository.list_users()}
    assert "ada" in restored_users and restored_users["ada"].role == UserRole.administrator
    assert "rae" in restored_users and restored_users["rae"].role == UserRole.reviewer
    assert restored_repository.has_eligible_administrator() is True, (
        "restore must not accidentally reopen first-run admin bootstrap"
    )
    restored_audit = restored_repository.list_audit_log(limit=200)
    assert len(restored_audit) >= audit_before, "audit history restores with the observatory"
    assert any(entry.action == "backup.restored" for entry in restored_audit)
    assert restored_repository.get_installation_settings().installation_name == "Test Yard"

    # The durable password hash survives -- a fresh sign-in still works.
    assert restored_repository.authenticate_user(
        SignInRequest(login_identity="rae", password="reviewer-password-1")
    ) is not None

    # An ephemeral session token issued *before* the restore is not
    # expected to keep resolving against the newly-opened repository
    # object post-restore -- see docs/local-identity-multi-user-contract.md
    # "Backup/restore identity semantics" ("ephemeral active sessions do
    # not need to survive host replacement"). Whether or not it happens to
    # still resolve is not the contract; durable identity surviving is.
    restored_repository.resolve_session(reviewer_signed_in_token)  # must not raise
