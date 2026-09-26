"""Test-suite-wide safety net (Test / Development Repository Isolation v1
-- see docs/test-repository-isolation-contract.md).

MockingBird has no application-level "test mode": `get_repository()`
(`mockingbird.api.main`) is a lazy module-global singleton that, left
unconfigured, constructs a `ProductRepository()` against the *default*
database/media path -- the same relative `data/mockingbird.sqlite3` a real
local checkout uses (`mockingbird.storage.database.DEFAULT_DB_URL`). Most
test files that talk to the repository already define their own
`tmp_path`-backed isolation fixture (a real, working, established
convention this file does not replace or refactor); this autouse fixture
is the repo-wide default for any test that does not -- current or future
-- so the *unconfigured* starting point is always isolated storage rather
than "whatever the module happened to leave behind."

This is one of two independent layers, not the only one:
`mockingbird.storage.database`'s `UnsafeDefaultStorageAccessError` guard is
the other, and it is load-bearing on its own -- it fails loudly even when a
test deliberately resets the singleton back to `None` mid-test (exactly
what the two real `run_preflight()` tests in `test_single_app_runtime.py`
and `test_windows_launcher_instance_identity.py` do, on purpose, to
exercise real default-resolution behavior). An autouse fixture cannot
protect against a test that intentionally undoes its own setup; the
storage-layer guard can, because it checks the *resolved path* itself
every time, not whether a fixture happened to run first.

Release Engineering Foundation v1 extended this same layer to
`MOCKINGBIRD_BACKUP_ROOT`: `ProductRepository` now creates a real, verified
`LocalBackupManager` backup (`kind="pre_migration"`) the moment any test
rewinds a database's recorded schema version and reopens it, since that is
exactly the "a real migration is about to run" condition this milestone's
pre-migration safety backup fires on. `LocalBackupManager`'s own default
`backup_root` (`storage/backup.py`'s `backup_root_from_env`) is the
*relative* path `data/backups` -- correct for a packaged app that already
`os.chdir()`d into its runtime home (`runtime.run_preflight`), but resolved
against pytest's own working directory (normally the repository root) for
every test that does not otherwise configure it. Without the env var set
here, any such test would silently write a real backup archive into this
checkout's own `data/backups/` -- exactly the class of bug this file exists
to prevent. Tests that care about backup behavior specifically already
construct their own explicit `backup_root=tmp_path / "..."` (see
`tests/test_persistence.py`, `tests/test_local_backup_recovery.py`) and are
unaffected by this default.
"""

from __future__ import annotations

import os
import time

import httpx
import pytest
from starlette.testclient import TestClient as _StarletteTestClient

from mockingbird.api import main as api_main
from mockingbird.api.main import configure_repository
from mockingbird.repository.product_repository import ProductRepository

_BACKUP_ROOT_ENV_VAR = "MOCKINGBIRD_BACKUP_ROOT"


def de_demo_seeded_source(repository: ProductRepository, *, source_id: str = "source-backyard-demo") -> None:
    """Give the seeded demo Source a real, non-demo effective provider.

    Native-Windows & Packaging Acceptance v1: real fresh-install testing
    found the seeded demo Source's own activity leaking into the real
    Review Queue/Dashboard counts (the same defect family Pre-Release
    Trust & Correctness Correction v1's UI-01 fix already closed for
    Dashboard "Recent activity"/Bird Log). The fix -- excluding
    `is_demo_source` activity at the Review Queue API boundary and in
    `dashboard_summary`'s own derivation -- has a real blast radius: many
    existing test files across this suite use the seeded demo Source/
    Stream purely as convenience plumbing (a Visit needs *some* Source),
    not as something under test, and now see it excluded too. This is
    UI-01's own already-established fix for exactly this situation ("a
    narrowly-scoped 'de-demo' of the seeded Source in place" -- see
    `mockingbird.repository.product_repository._real_source_condition`'s
    docstring): insert a real `SourceProviderConfigurationModel` row with
    a non-"demo" `provider_key` -- `"camera_node"`, the exact repurposing
    example that docstring itself names ("Guided Camera Editing
    repurposing the seeded demo Source into a real `camera_node` Source"),
    not a fabricated provider key, so any test that happens to also touch
    provider-definition/playback-status resolution for this Source sees a
    real, recognized value (a Source's own `kind` staying `"demo"` forever
    is expected and unrelated -- only the *effective* provider decides
    this). Call once, right after seeding,
    from a file's own repository-isolation fixture; every test in that
    file then sees the seeded Visits as real history again, exactly as
    every test in every affected file already assumed before this
    milestone's own fix existed.
    """

    from datetime import UTC, datetime

    from mockingbird.repository.product_repository import SourceProviderConfigurationModel

    with repository.session_factory() as session:
        with session.begin():
            existing = session.get(SourceProviderConfigurationModel, source_id)
            if existing is not None:
                existing.provider_key = "camera_node"
                existing.updated_at = datetime.now(UTC)
            else:
                session.add(
                    SourceProviderConfigurationModel(
                        source_id=source_id,
                        provider_key="camera_node",
                        config_json="{}",
                        updated_at=datetime.now(UTC),
                    )
                )


@pytest.fixture(autouse=True)
def _default_isolated_repository(tmp_path_factory: pytest.TempPathFactory):
    """Configure a throwaway, isolated repository before every test runs.

    Deliberately requests `tmp_path_factory` (a fresh, uniquely-numbered
    directory *outside* any test's own `tmp_path` tree) rather than the
    test's own `tmp_path` fixture: a real regression caught this the other
    way around -- nesting under `tmp_path` directly made
    `test_probe_never_leaves_its_sentinel_file_behind` see this fixture's
    own subdirectory and fail an unrelated "tmp_path started/ended empty"
    assertion. `tmp_path_factory.mktemp` guarantees a fresh path on every
    call (`numbered=True` by default), so this can never collide with a
    test's own `tmp_path` state, another test's isolation directory, or
    itself across parametrized re-invocations.

    Pytest instantiates this conftest-level autouse fixture first (broader
    scope), then any test-module-local autouse fixture runs second and
    simply reconfigures over top of this one for that test
    (`configure_repository` closes the previous repository whenever it is
    replaced, so nothing here leaks a connection). Teardown mirrors that:
    if something else already replaced or cleared the singleton by the
    time this fixture unwinds, this only closes its own repository object
    directly instead of touching whatever is active now -- never
    double-tearing-down another fixture's state.

    Points the default *pre-migration backup* root at this same isolated
    directory for the duration of this fixture -- see the module docstring
    above -- restored by hand in the `finally` block below, deliberately
    **not** via `monkeypatch.setenv`: adding a `monkeypatch` dependency to
    this specific autouse fixture (present on literally every test in the
    suite) was tried first and confirmed, by direct clean-baseline-vs-
    changed-only bisection, to shift this fixture's own position in
    pytest's per-test fixture-teardown order enough to expose a real,
    pre-existing, unrelated test-isolation fragility in
    `tests/test_camera_health.py`/`tests/test_stream_monitoring_contract.py`
    (each manually saves/restores `api_main._live_camera_session_manager`
    around a test rather than using `monkeypatch`'s own auto-revert) as two
    new teardown-only errors in `tests/test_stream_playback_contract.py`.
    Plain `os.environ` get/set/restore carries no such fixture-graph side
    effect and does not reproduce it -- confirmed directly. This is a
    genuine, narrow finding about pytest fixture-teardown ordering, not a
    reason to believe `monkeypatch.setenv` is unsafe in general.

    This is deliberately a different physical directory than a test's own
    explicit `db_url`/`media_root` when one is configured; that is harmless,
    since the only property that matters here is "never the real repository-
    relative default," not "the same tmp root as this test's own data."
    """

    isolation_root = tmp_path_factory.mktemp("default_isolation")
    previous_backup_root = os.environ.get(_BACKUP_ROOT_ENV_VAR)
    os.environ[_BACKUP_ROOT_ENV_VAR] = str(isolation_root / "backups")
    repository = ProductRepository(
        db_url=f"sqlite:///{isolation_root / 'mockingbird.sqlite3'}",
        media_root=isolation_root / "media",
    )
    configure_repository(repository)
    try:
        yield repository
    finally:
        if previous_backup_root is None:
            os.environ.pop(_BACKUP_ROOT_ENV_VAR, None)
        else:
            os.environ[_BACKUP_ROOT_ENV_VAR] = previous_backup_root
        if api_main._repository is repository:
            configure_repository(None)
        else:
            repository.close()


# --- Local Identity, Multi-User & Organization Access v1: shared legacy-
# HTTP-test authentication (see docs/local-identity-multi-user-contract.md
# "Authorization") -------------------------------------------------------
#
# `mockingbird.api.auth` enforces the real Viewer/Reviewer/Administrator
# policy on every request, unconditionally -- production request handling
# never infers "a test is running" from ambient process state, and there is
# no implicit synthetic actor (see that module's own docstring). Roughly
# 100 test files predate that milestone and call protected endpoints over
# real HTTP with no session of their own. `LegacyAuthenticatedTestClient`
# is the one place their needed session gets minted -- the same way a real
# client gets one, via a genuine `POST /api/setup/administrator` bootstrap
# (or, if this test's repository already has an Administrator, a genuine
# `POST /api/auth/sign-in`) -- never a synthetic identity and never a
# direct database row. It is opt-in strictly by test construction: a test
# file chooses this class in place of plain `httpx.AsyncClient` in its own
# fixture; nothing about it is triggered merely by pytest running.
#
# The real HTTP call happens lazily, on this client's first actual request,
# rather than eagerly at construction time: most of these test files
# configure their own isolated repository via their own fixture (rather
# than relying on `_default_isolated_repository` above), and pytest does
# not guarantee that fixture has already run before this one's own setup
# runs -- only before the test body itself starts. Deferring to first use
# sidesteps every one of those files needing to declare that dependency
# explicitly.
#
# Tests that care WHICH identity/role is signed in, that must observe a
# real 401/403 or no-administrator-yet state, or that need more than one
# distinct signed-in identity, must not use these classes -- construct a
# plain `httpx.AsyncClient`/`TestClient` and drive
# `/api/setup/administrator` + `/api/auth/sign-in` explicitly instead. See
# `tests/test_local_identity_multi_user.py` for that real, explicit
# pattern.
#
# Both classes key their cached session on `id(api_main._repository)`,
# re-authenticating whenever it changes, rather than authenticating only
# once per client instance: a handful of these pre-existing test files
# share *one* client object at module scope across many tests, each of
# which gets its own fresh repository from `_default_isolated_repository`
# above -- a session cached "for the life of this client object" would
# silently 401 every test after the first. Checking the live repository
# identity instead makes both a one-client-per-test and a one-client-per-
# module test file correct without either needing to know which shape the
# other is, and also re-authenticates correctly for the rare test that
# swaps the repository singleton itself mid-test (for example a real
# `POST .../backups/{id}/restore`, which calls `configure_repository`
# again). It deliberately does NOT re-authenticate just because a *prior*
# request through the same still-current repository already did --
# needlessly minting a fresh session (a real write) on every call would
# itself read as a side effect to any test asserting one of its calls has
# none (see `tests/test_cross_install_backup_restore.py`).
#
# That `id()` check is a fast-path only, not the sole guarantee: CPython
# reuses a freed object's address, and this suite's own fixture teardown
# really does close/drop/garbage-collect a repository between tests --
# confirmed by direct execution that a later test's fresh repository can
# receive the exact same `id()` a since-closed earlier one had, which
# would make the check above wrongly believe the client is still
# authenticated for it. Both classes' `request()` self-heals for this: a
# 401 despite believing we are already authenticated re-authenticates for
# real and retries exactly once, rather than trusting the cache blindly.

_LEGACY_TEST_ADMINISTRATOR_DISPLAY_NAME = "Legacy Test Administrator"
_LEGACY_TEST_ADMINISTRATOR_LOGIN_IDENTITY = "legacy-test-administrator"
_LEGACY_TEST_ADMINISTRATOR_PASSWORD = "legacy-test-administrator-password-1"

_LEGACY_ADMINISTRATOR_BOOTSTRAP_BODY = {
    "display_name": _LEGACY_TEST_ADMINISTRATOR_DISPLAY_NAME,
    "login_identity": _LEGACY_TEST_ADMINISTRATOR_LOGIN_IDENTITY,
    "password": _LEGACY_TEST_ADMINISTRATOR_PASSWORD,
}
_LEGACY_ADMINISTRATOR_SIGN_IN_BODY = {
    "login_identity": _LEGACY_TEST_ADMINISTRATOR_LOGIN_IDENTITY,
    "password": _LEGACY_TEST_ADMINISTRATOR_PASSWORD,
}


def _legacy_session_conflict_error(bootstrap_status: int, sign_in_status: int) -> RuntimeError:
    return RuntimeError(
        "Legacy authenticated test client: this test's repository already has an "
        "Administrator under a different identity than the shared legacy default "
        f"({bootstrap_status} bootstrapping, {sign_in_status} signing in) -- sign in "
        "explicitly for this test instead of using this shared client."
    )


class LegacyAuthenticatedTestClient(httpx.AsyncClient):
    """Drop-in `httpx.AsyncClient` replacement for pre-existing HTTP test
    fixtures that need *some* signed-in identity and do not care which --
    see the module comment above. Takes exactly the same constructor
    arguments as `httpx.AsyncClient` (no `__init__` override)."""

    _legacy_authenticated_repository_id: int | None = None

    async def request(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201 - matches httpx's own untyped override target
        current_repository_id = id(api_main._repository)
        if self._legacy_authenticated_repository_id != current_repository_id:
            await self._ensure_legacy_administrator_session()
            self._legacy_authenticated_repository_id = current_repository_id
        response = await super().request(*args, **kwargs)
        if response.status_code == 401:
            # Self-healing fallback for the `id()`-reuse hazard described
            # in the module comment above: confirmed by direct execution
            # (a 30-iteration close/GC-churn repro against this exact
            # class reliably reproduces the collision) that CPython *does*
            # reuse a freed repository's address for a later one across
            # this suite's own real fixture-teardown/garbage-collection
            # churn -- which would make the cache check above wrongly skip
            # re-authenticating. A 401 despite believing we are already
            # authenticated for the live repository means that belief was
            # wrong; authenticate for real and retry exactly once.
            await self._ensure_legacy_administrator_session()
            self._legacy_authenticated_repository_id = current_repository_id
            response = await super().request(*args, **kwargs)
        return response

    async def _ensure_legacy_administrator_session(self) -> None:
        bootstrap = await super().request(
            "POST", "/api/setup/administrator", json=_LEGACY_ADMINISTRATOR_BOOTSTRAP_BODY
        )
        if bootstrap.status_code == 201:
            return
        # An Administrator already exists in this test's repository (this
        # test's own fixture created one before its first request through
        # this client) -- sign in for real instead of assuming which
        # credentials it has.
        signed_in = await super().request(
            "POST", "/api/auth/sign-in", json=_LEGACY_ADMINISTRATOR_SIGN_IN_BODY
        )
        if signed_in.status_code != 200:
            raise _legacy_session_conflict_error(bootstrap.status_code, signed_in.status_code)


class LegacyAuthenticatedSyncTestClient(_StarletteTestClient):
    """Sync `starlette.testclient.TestClient`/`fastapi.testclient.TestClient`
    counterpart to `LegacyAuthenticatedTestClient` above, for the smaller
    set of pre-existing test files built on the synchronous client instead
    -- same behavior, same rationale, same opt-in-by-construction contract.
    Built on top of, not instead of, this project's own pre-existing
    `_patch_testclient_for_pytest` ASGI-transport compatibility patch
    (`mockingbird.api.main`, unrelated to authentication) -- that patch
    replaces `StarletteTestClient`'s methods in place, so this subclass's
    `super().request(...)` already resolves to the patched implementation.

    That patch is also why this class -- unlike the plain `httpx.
    AsyncClient`-based `LegacyAuthenticatedTestClient` above, which needs
    no such thing -- has to carry cookies forward itself: confirmed by
    direct execution that its `request()` rebuilds a brand new, cookie-
    less `httpx.AsyncClient` on every single call (a real, pre-existing
    characteristic of that ASGI-transport-hang workaround, unrelated to
    and predating this milestone), so `self.cookies` never actually
    accumulates a `Set-Cookie` on its own. `_request_and_capture_cookies`
    below is the one place this class closes that gap, entirely on the
    test-infrastructure side -- the pre-existing patch itself is left
    untouched."""

    _legacy_authenticated_repository_id: int | None = None

    def request(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201 - matches httpx's own untyped override target
        current_repository_id = id(api_main._repository)
        if self._legacy_authenticated_repository_id != current_repository_id:
            self._ensure_legacy_administrator_session()
            self._legacy_authenticated_repository_id = current_repository_id
        response = self._request_and_capture_cookies(*args, **kwargs)
        if response.status_code == 401:
            # See `LegacyAuthenticatedTestClient.request`'s own comment --
            # the same `id()`-reuse hazard applies here, confirmed by the
            # same repro against this synchronous class too.
            self._ensure_legacy_administrator_session()
            self._legacy_authenticated_repository_id = current_repository_id
            response = self._request_and_capture_cookies(*args, **kwargs)
        return response

    def _request_and_capture_cookies(self, *args, **kwargs):  # noqa: ANN002, ANN003, ANN201
        response = super().request(*args, **kwargs)
        self.cookies.update(response.cookies)
        return response

    def _ensure_legacy_administrator_session(self) -> None:
        bootstrap = self._request_and_capture_cookies(
            "POST", "/api/setup/administrator", json=_LEGACY_ADMINISTRATOR_BOOTSTRAP_BODY
        )
        if bootstrap.status_code == 201:
            return
        signed_in = self._request_and_capture_cookies(
            "POST", "/api/auth/sign-in", json=_LEGACY_ADMINISTRATOR_SIGN_IN_BODY
        )
        if signed_in.status_code != 200:
            raise _legacy_session_conflict_error(bootstrap.status_code, signed_in.status_code)


@pytest.fixture
def new_york_host_timezone():
    """Pin this process's *host-local* timezone to America/New_York for one
    test (CI & Core Validation Closure v1).

    MockingBird has no per-Place timezone setting: "local" is whatever the
    host resolves (`mockingbird.time_utils.resolve_host_local_timezone`,
    whose first candidate is the `TZ` environment variable, and plain
    `datetime.astimezone()`, which reads the C library's local zone). A
    test whose fixture was authored against a real America/New_York host
    -- hour buckets, local-midnight boundaries, "EST"/"EDT" labels --
    encodes that zone in its expectations, so it must state the zone
    explicitly rather than assume the machine it happens to run on; the
    hosted Linux runner is UTC. `time.tzset()` is what makes the C-library
    path honor the new `TZ` immediately (POSIX only; on Windows the
    variable alone is honored). The previous value is restored, and
    `tzset()` re-run, on teardown -- no zone leaks into the next test."""

    previous = os.environ.get("TZ")
    os.environ["TZ"] = "America/New_York"
    if hasattr(time, "tzset"):
        time.tzset()
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = previous
        if hasattr(time, "tzset"):
            time.tzset()
