"""Login Rate-Limiting & Authentication Abuse Resistance v1 -- full
product-integration suite through `ProductRepository.authenticate_user` and
real `POST /api/auth/sign-in` HTTP calls (see docs/local-identity-multi-
user-contract.md "Login rate limiting" and docs/login-rate-limiting-
authentication-abuse-resistance-v1-report.md).

See tests/test_login_rate_limiter.py for the pure-unit suite covering
`LoginRateLimiter` in isolation (no database, no HTTP). This file instead
proves the real wiring: the repository/endpoint boundary, real audit rows,
real (non-)session creation, and the exact HTTP response contract.

A deterministic, manually-advanced fake clock is injected into every
repository built here (`login_rate_limiter=LoginRateLimiter(clock=...)`) --
no real sleeps anywhere in this file, per the governing brief's own
"Clock / timing" requirement.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from sqlalchemy import func, select

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    AdministratorBootstrapRequest,
    SignInRequest,
    UserCreate,
    UserEnabledUpdate,
    UserRole,
)
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.security.login_rate_limiter import (
    LOGIN_THROTTLE_DELAY_LADDER_SECONDS,
    LOGIN_THROTTLE_FREE_ATTEMPTS,
    LoginRateLimiter,
)
from mockingbird.storage.models import UserSessionModel

pytestmark = pytest.mark.anyio

ADMIN_PASSWORD = "correct horse battery"  # noqa: S105 - test fixture credential, not a real secret


class FakeClock:
    def __init__(self, start: float = 1_000.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def isolated_repository(tmp_path: Path, fake_clock: FakeClock) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
        login_rate_limiter=LoginRateLimiter(clock=fake_clock),
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def http_client(source_host: str = "127.0.0.1") -> httpx.AsyncClient:
    """A real HTTP client against the real ASGI app, with a controllable
    simulated direct TCP peer address -- see `httpx.ASGITransport`'s own
    `client` parameter. Different `source_host` values simulate genuinely
    different requesting devices for the multi-source tests below."""

    transport = httpx.ASGITransport(app=app, client=(source_host, 12345))
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def session_row_count(repository: ProductRepository) -> int:
    with repository.session_factory() as session:
        return session.scalar(select(func.count(UserSessionModel.id))) or 0


# --- Normal success / single failure ------------------------------------------


async def test_valid_credentials_succeed_immediately(isolated_repository: ProductRepository) -> None:
    isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password=ADMIN_PASSWORD)
    )
    result = isolated_repository.authenticate_user(
        SignInRequest(login_identity="ada", password=ADMIN_PASSWORD), source_ip="203.0.113.1"
    )
    assert result is not None
    current_user, token = result
    assert current_user.login_identity == "ada"
    assert isolated_repository.resolve_session(token) is not None


async def test_single_wrong_password_returns_generic_failure_and_creates_no_session(
    isolated_repository: ProductRepository,
) -> None:
    isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password=ADMIN_PASSWORD)
    )
    baseline_sessions = session_row_count(isolated_repository)  # bootstrap itself mints one session

    result = isolated_repository.authenticate_user(
        SignInRequest(login_identity="ada", password="totally wrong"), source_ip="203.0.113.1"
    )
    assert result is None
    assert session_row_count(isolated_repository) == baseline_sessions, "a failed attempt must create no session"


# --- Enumeration safety (governing brief Sec 17) -------------------------------


async def test_unknown_user_wrong_password_and_throttled_are_indistinguishable_over_http() -> None:
    async with http_client() as admin_client:
        bootstrap = await admin_client.post(
            "/api/setup/administrator",
            json={"display_name": "Ada Admin", "login_identity": "ada", "password": ADMIN_PASSWORD},
        )
        assert bootstrap.status_code == 201

        # (a) A username that has never existed.
        unknown_response = await admin_client.post(
            "/api/auth/sign-in", json={"login_identity": "nobody-here", "password": "whatever12345"}
        )

        # (b) A real, distinct account with one wrong-password attempt
        # (deliberately a different account than (c) below, so this
        # single-failure case is not itself influenced by the throttle
        # (c) is about to build up).
        create_eve = await admin_client.post(
            "/api/admin/users",
            json={
                "display_name": "Eve",
                "login_identity": "eve",
                "password": "eve-password-123",
                "role": "viewer",
            },
        )
        assert create_eve.status_code == 201
        wrong_password_response = await admin_client.post(
            "/api/auth/sign-in", json={"login_identity": "eve", "password": "not eve's password"}
        )

        # (c) A real account, currently throttled, tried with its
        # genuinely CORRECT password.
        for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 1):
            await admin_client.post(
                "/api/auth/sign-in", json={"login_identity": "ada", "password": "still wrong"}
            )
        throttled_response = await admin_client.post(
            "/api/auth/sign-in", json={"login_identity": "ada", "password": ADMIN_PASSWORD}
        )

    for response in (unknown_response, wrong_password_response, throttled_response):
        assert response.status_code == 401
        assert response.json() == {"detail": "Incorrect login identity or password."}
        assert "mb_session" not in response.cookies


# --- Repeated same-account failures / progressive throttle ---------------------


async def test_repeated_same_account_failures_activate_throttle_blocking_even_the_correct_password(
    isolated_repository: ProductRepository, fake_clock: FakeClock
) -> None:
    isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password=ADMIN_PASSWORD)
    )
    baseline_sessions = session_row_count(isolated_repository)  # bootstrap itself mints one session

    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS):
        result = isolated_repository.authenticate_user(
            SignInRequest(login_identity="ada", password="wrong"), source_ip="203.0.113.1"
        )
        assert result is None  # free attempts: ordinary failure, no throttle activated yet

    # One more failure crosses the free-attempts budget.
    result = isolated_repository.authenticate_user(
        SignInRequest(login_identity="ada", password="wrong"), source_ip="203.0.113.1"
    )
    assert result is None

    # Even the genuinely correct password is now rejected while throttled.
    result = isolated_repository.authenticate_user(
        SignInRequest(login_identity="ada", password=ADMIN_PASSWORD), source_ip="203.0.113.1"
    )
    assert result is None
    assert session_row_count(isolated_repository) == baseline_sessions, (
        "no failed or throttled attempt may create a session"
    )

    # Waiting out the cooldown restores normal behavior.
    fake_clock.advance(LOGIN_THROTTLE_DELAY_LADDER_SECONDS[0] + 0.01)
    result = isolated_repository.authenticate_user(
        SignInRequest(login_identity="ada", password=ADMIN_PASSWORD), source_ip="203.0.113.1"
    )
    assert result is not None


# --- Username spray from one source --------------------------------------------


async def test_username_spray_across_many_accounts_from_one_source_is_bounded_over_http() -> None:
    async with http_client(source_host="198.51.100.7") as client:
        bootstrap = await client.post(
            "/api/setup/administrator",
            json={"display_name": "Ada Admin", "login_identity": "ada", "password": ADMIN_PASSWORD},
        )
        assert bootstrap.status_code == 201

        for index in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 2):
            response = await client.post(
                "/api/auth/sign-in",
                json={"login_identity": f"fake-user-{index}", "password": "whatever12345"},
            )
            assert response.status_code == 401

        # A brand new, never-before-tried username from the same source.
        response = await client.post(
            "/api/auth/sign-in",
            json={"login_identity": "yet-another-fake-user", "password": "whatever12345"},
        )
        assert response.status_code == 401
        assert response.json() == {"detail": "Incorrect login identity or password."}


# --- Distributed / multi-source spray, and no permanent lockout ----------------


async def test_distributed_spray_is_bounded_but_never_permanently_locks_the_account(
    isolated_repository: ProductRepository, fake_clock: FakeClock
) -> None:
    """One abusive source hammering a real account must not be able to
    permanently deny that account to a different, legitimate source --
    governing brief Sec 6/Sec 16 "Multiple sources"."""

    isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password=ADMIN_PASSWORD)
    )

    # Source A sprays wrong passwords against "ada" past the throttle
    # threshold.
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 1):
        isolated_repository.authenticate_user(
            SignInRequest(login_identity="ada", password="wrong"), source_ip="203.0.113.50"
        )

    # Source B -- a different address entirely -- tries "ada" with the
    # genuinely correct password immediately after. The account-keyed
    # dimension is shared across sources by design (it is what makes a
    # distributed spray bounded at all), so this is *also* throttled right
    # now -- a short, disclosed, bounded collateral cooldown, never a
    # permanent lock.
    result = isolated_repository.authenticate_user(
        SignInRequest(login_identity="ada", password=ADMIN_PASSWORD), source_ip="198.51.100.99"
    )
    assert result is None

    # Ordinary time advancement -- not a new mechanism, not an unlock
    # override -- always restores access for the legitimate source.
    fake_clock.advance(LOGIN_THROTTLE_DELAY_LADDER_SECONDS[0] + 0.01)
    result = isolated_repository.authenticate_user(
        SignInRequest(login_identity="ada", password=ADMIN_PASSWORD), source_ip="198.51.100.99"
    )
    assert result is not None


# --- Success reset --------------------------------------------------------------


async def test_success_after_failures_clears_state_and_audits_recovery(
    isolated_repository: ProductRepository,
) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password=ADMIN_PASSWORD)
    )
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS):
        isolated_repository.authenticate_user(
            SignInRequest(login_identity="ada", password="wrong"), source_ip="203.0.113.1"
        )

    result = isolated_repository.authenticate_user(
        SignInRequest(login_identity="ada", password=ADMIN_PASSWORD), source_ip="203.0.113.1"
    )
    assert result is not None

    audit = isolated_repository.list_audit_log()
    recovery_events = [entry for entry in audit if entry.action == "auth.login_succeeded_after_failures"]
    assert len(recovery_events) == 1
    assert recovery_events[0].metadata == {"cleared_failure_count": LOGIN_THROTTLE_FREE_ATTEMPTS}
    assert recovery_events[0].target_id == admin.id

    # State was genuinely cleared -- a fresh round needs the full budget again.
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS):
        result = isolated_repository.authenticate_user(
            SignInRequest(login_identity="ada", password="wrong"), source_ip="203.0.113.1"
        )
        assert result is None
    still_correct = isolated_repository.authenticate_user(
        SignInRequest(login_identity="ada", password=ADMIN_PASSWORD), source_ip="203.0.113.1"
    )
    assert still_correct is not None


# --- Restart semantics ----------------------------------------------------------


async def test_a_fresh_repository_has_no_memory_of_prior_throttle_state(tmp_path: Path) -> None:
    """Documents the chosen persistence contract directly: throttle state
    is in-memory only and belongs to one `LoginRateLimiter` instance, not
    to the database -- so a fresh `ProductRepository` (standing in for a
    process restart, or a backup-restore singleton swap; both already reset
    other in-memory session-adjacent state the identical way -- see
    `LoginRateLimiter`'s own module docstring) never inherits it, even
    against the same on-disk database."""

    db_url = f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}"
    media_root = tmp_path / "media"

    first_clock = FakeClock()
    first_repository = ProductRepository(
        db_url=db_url, media_root=media_root, login_rate_limiter=LoginRateLimiter(clock=first_clock)
    )
    first_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password=ADMIN_PASSWORD)
    )
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 1):
        first_repository.authenticate_user(
            SignInRequest(login_identity="ada", password="wrong"), source_ip="203.0.113.1"
        )
    still_throttled = first_repository.authenticate_user(
        SignInRequest(login_identity="ada", password=ADMIN_PASSWORD), source_ip="203.0.113.1"
    )
    assert still_throttled is None  # confirmed genuinely throttled before "restart"
    first_repository.close()

    # A brand new process-equivalent repository against the identical
    # database file -- the user row (and its password) survived; the
    # throttle state did not.
    second_repository = ProductRepository(
        db_url=db_url, media_root=media_root, login_rate_limiter=LoginRateLimiter(clock=FakeClock())
    )
    try:
        result = second_repository.authenticate_user(
            SignInRequest(login_identity="ada", password=ADMIN_PASSWORD), source_ip="203.0.113.1"
        )
        assert result is not None
    finally:
        second_repository.close()


# --- Disabled user ---------------------------------------------------------------


async def test_disabled_user_login_attempt_is_throttled_like_any_other_failure(
    isolated_repository: ProductRepository,
) -> None:
    admin, _ = isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password=ADMIN_PASSWORD)
    )
    viewer = isolated_repository.create_user(
        UserCreate(display_name="Vic Viewer", login_identity="vic", password="viewer-password-1", role=UserRole.viewer),
        acting_user=admin,
    )
    isolated_repository.set_user_enabled(viewer.id, UserEnabledUpdate(enabled=False), acting_user=admin)
    baseline_sessions = session_row_count(isolated_repository)  # bootstrap itself mints one session

    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 1):
        result = isolated_repository.authenticate_user(
            SignInRequest(login_identity="vic", password="viewer-password-1"), source_ip="203.0.113.1"
        )
        assert result is None
    decision_blocked = isolated_repository.authenticate_user(
        SignInRequest(login_identity="vic", password="viewer-password-1"), source_ip="203.0.113.1"
    )
    assert decision_blocked is None
    assert session_row_count(isolated_repository) == baseline_sessions


# --- Audit safety -----------------------------------------------------------------


async def test_audit_log_records_failures_and_throttle_activation_with_no_secrets(
    isolated_repository: ProductRepository,
) -> None:
    isolated_repository.create_first_administrator(
        AdministratorBootstrapRequest(display_name="Ada Admin", login_identity="ada", password=ADMIN_PASSWORD)
    )
    secret_password = "super-secret-password-1"  # noqa: S105 - test fixture credential
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 1):
        isolated_repository.authenticate_user(
            SignInRequest(login_identity="ada", password=secret_password), source_ip="203.0.113.1"
        )

    # `list_audit_log` orders newest-first (see its own docstring), so the
    # throttle-activation event -- chronologically the *last* of the four
    # attempts -- is expected at index 0 here.
    audit = isolated_repository.list_audit_log()
    login_events = [entry for entry in audit if entry.action.startswith("auth.login_")]
    assert [entry.action for entry in login_events] == [
        "auth.login_throttled",
        "auth.login_failed",
        "auth.login_failed",
        "auth.login_failed",
    ]
    assert login_events[0].metadata["account_failure_count"] == LOGIN_THROTTLE_FREE_ATTEMPTS + 1

    # The raw password must never appear anywhere in the audit trail, and
    # no entry's metadata may carry a "password" or "token" field at all.
    serialized = repr(audit)
    assert secret_password not in serialized
    for entry in audit:
        if entry.metadata:
            assert "password" not in entry.metadata
            assert "token" not in entry.metadata
