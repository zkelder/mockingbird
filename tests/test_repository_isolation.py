"""Test / Development Repository Isolation v1 (see
docs/test-repository-isolation-contract.md).

Proves the invariant this milestone exists to guarantee: an automated test
can never silently fall back to MockingBird's persistent development/
product database merely because a fixture or caller forgot to inject an
isolated repository. Every path here uses a safe sentinel `tmp_path`, never
the real checkout's `data/mockingbird.sqlite3` -- some tests below
deliberately exercise the *fallback-resolution* code path (chdir'd into the
real checkout root) but only ever call the pure, no-I/O `resolve_*`
functions directly, which raise before any engine/file is ever touched.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
import shutil
import tempfile

import httpx
import pytest
from sqlalchemy import create_engine

from mockingbird.api import main as api_main
from mockingbird.api.main import app, configure_repository, drain_background_tasks
from mockingbird.api.schemas import CameraSourceCreate
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage import database as database_module
from mockingbird.storage.database import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    DB_URL_ENV_VAR,
    DEFAULT_DB_URL,
    DEFAULT_MEDIA_ROOT,
    MEDIA_ROOT_ENV_VAR,
    UnsafeDefaultStorageAccessError,
    initialize_database,
    resolve_database_url,
    resolve_media_root,
)

# The real checkout's persistent dev database this whole milestone protects.
# Read-only path arithmetic only (`Path.resolve()` never creates or opens
# anything) -- used here only to assert test-triggered paths are NOT this
# path, never to open it.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_REAL_DEV_DB_PATH = _REPO_ROOT / "data" / "mockingbird.sqlite3"


def _clear_storage_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DB_URL_ENV_VAR, raising=False)
    monkeypatch.delenv(MEDIA_ROOT_ENV_VAR, raising=False)


# --- Part 4.1 / 4.2: default access is isolated or fails closed --------


def test_default_isolated_repository_fixture_is_a_real_working_isolated_repository(
    _default_isolated_repository: ProductRepository,
    tmp_path: Path,
) -> None:
    """The autouse conftest fixture is not a stub: it is a real repository
    under the system temp root, never under the checkout's real `data/`
    directory -- and, regression for a real bug this milestone caught
    (`test_storage_status_disk.py::test_probe_never_leaves_its_sentinel_
    file_behind`), never nested inside *this test's own* `tmp_path` either,
    since a test is entitled to assume its own `tmp_path` starts empty."""

    resolved_db_path = Path(_default_isolated_repository.db_url.removeprefix("sqlite:///")).resolve()
    assert resolved_db_path.is_relative_to(Path(tempfile.gettempdir()).resolve())
    assert resolved_db_path != _REAL_DEV_DB_PATH.resolve()
    assert not resolved_db_path.is_relative_to(tmp_path.resolve())
    assert _default_isolated_repository.media_root.resolve().is_relative_to(
        Path(tempfile.gettempdir()).resolve()
    )
    assert not _default_isolated_repository.media_root.resolve().is_relative_to(tmp_path.resolve())

    # A real, working repository, not a placeholder: it already seeded the
    # normal first-run demo content and answers a real read.
    status = _default_isolated_repository.local_data_status()
    assert status.database_ready is True
    assert status.database_schema_version == CURRENT_DATABASE_SCHEMA_VERSION


async def _get(path: str) -> httpx.Response:
    # `httpx.ASGITransport` only implements the async transport interface,
    # matching the pattern `tests/test_api.py`'s `ASGITestClient` and
    # `tests/test_observation_engine.py` already establish for this exact
    # ASGI-without-lifespan request shape.
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path)


def test_api_endpoint_with_no_explicit_repository_never_reports_the_real_dev_database() -> None:
    """An API test that defines *no* isolation fixture of its own (this file
    relies solely on the autouse default from conftest.py) must still never
    be able to reach the real persistent database through a normal request."""

    response = asyncio.run(_get("/api/settings/local-data"))

    assert response.status_code == 200
    payload = response.json()
    reported_path = Path(payload["database_path"]).resolve()
    assert reported_path != _REAL_DEV_DB_PATH.resolve()
    # The strong assertion: it is the isolated default (under the system
    # temp root, exactly what the storage-layer guard itself treats as
    # safe), not the real checkout's tracked `data/` directory.
    assert reported_path.is_relative_to(Path(tempfile.gettempdir()).resolve())
    assert not str(reported_path).startswith(str(_REPO_ROOT / "data"))


def test_unconfigured_default_fails_closed_under_pytest(monkeypatch: pytest.MonkeyPatch) -> None:
    """With no explicit db_url and no env var, the bare default database
    resolution must refuse itself while running under pytest -- this is the
    same guard that protects any future test which forgets isolation."""

    _clear_storage_env(monkeypatch)
    with pytest.raises(UnsafeDefaultStorageAccessError):
        resolve_database_url()


def test_unconfigured_media_root_default_is_deliberately_not_guarded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Scope boundary, not an oversight: unlike the database default,
    resolving the default media root never opens/writes anything by
    itself, and roughly a sixth of the existing suite already omits an
    explicit `media_root=` (relying on this exact fallback) without ever
    touching real media -- see `media_root_from_env`'s own docstring. This
    pins that deliberate asymmetry down as a regression, not silently."""

    _clear_storage_env(monkeypatch)
    assert str(resolve_media_root()) == "data/media/imports"


def test_dangerous_default_is_caught_even_when_cwd_is_the_real_checkout_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact scenario this milestone traced: CWD is the real checkout
    root (as it is for an ordinary `pytest` invocation) and nothing
    configured isolation. This must raise, not open the real file -- proven
    without ever letting `ProductRepository`/`create_engine` run."""

    _clear_storage_env(monkeypatch)
    monkeypatch.chdir(_REPO_ROOT)
    with pytest.raises(UnsafeDefaultStorageAccessError) as excinfo:
        resolve_database_url()
    assert str(_REAL_DEV_DB_PATH.resolve()) in str(excinfo.value)


# --- Part 4.6 / Part 2: explicit opt-in and real startup remain valid ---


def test_explicit_db_url_and_env_var_are_never_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A deliberate persistent-database integration fixture (an explicit
    argument, or an explicit env var) is never second-guessed by the guard,
    no matter what it points at -- proving the opt-in stays possible."""

    _clear_storage_env(monkeypatch)
    sentinel = f"sqlite:///{tmp_path / 'deliberate-integration.sqlite3'}"

    assert resolve_database_url(sentinel) == sentinel

    monkeypatch.setenv(DB_URL_ENV_VAR, sentinel)
    assert resolve_database_url() == sentinel

    sentinel_media = tmp_path / "deliberate-media"
    assert resolve_media_root(sentinel_media) == sentinel_media


def test_default_resolves_safely_once_cwd_is_an_isolated_runtime_home(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mirrors `runtime.run_preflight()`'s own real, already-existing safe
    pattern (`test_single_app_runtime.py`): once CWD is inside an isolated
    directory, the unconfigured default must keep resolving there without
    raising -- the guard must not break this legitimate existing behavior."""

    _clear_storage_env(monkeypatch)
    isolated_home = tmp_path / "runtime-home"
    isolated_home.mkdir()
    monkeypatch.chdir(isolated_home)

    # The returned URL string is still the same *relative* literal
    # (`DEFAULT_DB_URL`) either way -- the safety comes entirely from where
    # that relative path resolves given the current CWD, not from the
    # string differing. This must not raise, and must resolve under the
    # isolated home, never under the real checkout root.
    resolved = resolve_database_url()
    assert resolved == DEFAULT_DB_URL
    resolved_path = Path(resolved.removeprefix("sqlite:///")).resolve()
    assert resolved_path.is_relative_to(isolated_home.resolve())
    assert resolved_path != _REAL_DEV_DB_PATH.resolve()


def test_outside_pytest_the_default_resolves_normally_for_real_startup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Simulates real (non-test) product startup: with the pytest detection
    itself patched off, the default database/media resolution must behave
    exactly as it always has, unconditionally -- production and ordinary
    local dev startup are not test execution and must never be guarded."""

    _clear_storage_env(monkeypatch)
    monkeypatch.setattr(database_module, "_running_under_pytest", lambda: False)

    assert resolve_database_url() == DEFAULT_DB_URL
    assert str(resolve_media_root()) == DEFAULT_MEDIA_ROOT


# --- Part 4.3 / Part 5: migrations touch only the isolated fixture ------


def test_migrations_during_tests_apply_only_to_the_isolated_fixture(tmp_path: Path) -> None:
    """Construct a pre-migration (schema v20) fixture database, exactly the
    established `test_camera_health.py` pattern, and confirm the real dev
    database's on-disk facts are provably unchanged by running it."""

    real_db_existed_before = _REAL_DEV_DB_PATH.exists()
    baseline_stat = _REAL_DEV_DB_PATH.stat() if real_db_existed_before else None

    engine = create_engine(f"sqlite:///{tmp_path / 'v20-fixture.sqlite3'}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            "CREATE TABLE mockingbird_schema (singleton_id INTEGER PRIMARY KEY, "
            "version INTEGER NOT NULL, updated_at DATETIME NOT NULL)"
        )
        connection.exec_driver_sql(
            "INSERT INTO mockingbird_schema (singleton_id, version, updated_at) "
            "VALUES (1, 20, '2026-01-01 00:00:00')"
        )
        connection.exec_driver_sql("CREATE TABLE streams (id VARCHAR PRIMARY KEY)")
        # v21's `_migrate_to_camera_health_incidents` reflects this table's
        # existing columns before adding to them -- the exact fixture shape
        # `test_camera_health.py`'s own v20 migration test already
        # establishes, reused here rather than a narrower, incomplete copy.
        connection.exec_driver_sql(
            "CREATE TABLE stream_runtime_checkpoints ("
            "stream_id VARCHAR PRIMARY KEY, observed_policy_revision INTEGER NOT NULL, actual_state VARCHAR NOT NULL, "
            "app_instance_id VARCHAR, runtime_generation_id VARCHAR, last_start_attempt_at DATETIME, "
            "last_healthy_frame_at DATETIME, last_clean_stop_at DATETIME, last_failure_at DATETIME, "
            "failure_code VARCHAR, consecutive_failure_count INTEGER NOT NULL, next_retry_at DATETIME, "
            "last_stop_reason VARCHAR, start_count INTEGER NOT NULL, failure_count INTEGER NOT NULL, "
            "evidence_handoff_count INTEGER NOT NULL, safety_hold_active BOOLEAN NOT NULL, updated_at DATETIME NOT NULL)"
        )

    status = initialize_database(engine)

    assert status.version == CURRENT_DATABASE_SCHEMA_VERSION
    assert _REAL_DEV_DB_PATH.exists() == real_db_existed_before
    if baseline_stat is not None:
        after_stat = _REAL_DEV_DB_PATH.stat()
        assert after_stat.st_size == baseline_stat.st_size
        assert after_stat.st_mtime == baseline_stat.st_mtime


# --- Part 4.4 / Part 6: no sharing, no leakage, deterministic lifecycle -


def test_two_independent_default_style_repositories_do_not_share_state(tmp_path: Path) -> None:
    """Simulates "two different tests" relying on the same isolation
    pattern: independently constructed repositories at different tmp roots
    must never see each other's writes."""

    repo_a = ProductRepository(db_url=f"sqlite:///{tmp_path / 'a' / 'mockingbird.sqlite3'}")
    repo_b = ProductRepository(db_url=f"sqlite:///{tmp_path / 'b' / 'mockingbird.sqlite3'}")
    try:
        names_before = {source.name for source in repo_b.list_sources()}
        repo_a.create_camera_source(_marker_source_payload("marker-source-a-only"))
        assert "marker-source-a-only" in {s.name for s in repo_a.list_sources()}
        assert {source.name for source in repo_b.list_sources()} == names_before
        assert "marker-source-a-only" not in {source.name for source in repo_b.list_sources()}
    finally:
        repo_a.close()
        repo_b.close()


def test_repository_state_first_test_creates_a_marker_source(
    _default_isolated_repository: ProductRepository,
) -> None:
    """Paired with the `_second_test` below: proves the autouse fixture
    gives *separate pytest test functions* independent state, not just
    separate manually-constructed objects. Each half of this pair asserts
    only its own observed starting state, so the pair is order-independent
    -- neither half assumes the other ran first."""

    assert "marker-source-cross-test-leak-check" not in {
        source.name for source in _default_isolated_repository.list_sources()
    }
    _default_isolated_repository.create_camera_source(
        _marker_source_payload("marker-source-cross-test-leak-check")
    )
    assert "marker-source-cross-test-leak-check" in {
        source.name for source in _default_isolated_repository.list_sources()
    }


def test_repository_state_second_test_does_not_see_the_first_tests_marker(
    _default_isolated_repository: ProductRepository,
) -> None:
    """See `_first_test` above. Regardless of execution order, a fresh test
    relying only on the autouse default must never observe another test's
    marker record -- there is no shared global temp database."""

    assert "marker-source-cross-test-leak-check" not in {
        source.name for source in _default_isolated_repository.list_sources()
    }


def test_configure_repository_closes_the_previous_repository_when_replaced(
    tmp_path: Path,
) -> None:
    """Repository singleton lifecycle: replacing the active repository must
    close exactly the one being replaced, not leak it, and not touch the
    new one."""

    first = ProductRepository(db_url=f"sqlite:///{tmp_path / 'first.sqlite3'}")
    second = ProductRepository(db_url=f"sqlite:///{tmp_path / 'second.sqlite3'}")
    close_calls = []
    original_close = first.close

    def _spy_close() -> None:
        close_calls.append("first")
        original_close()

    first.close = _spy_close  # type: ignore[method-assign]

    try:
        configure_repository(first)
        assert close_calls == []
        configure_repository(second)
        assert close_calls == ["first"]
        assert api_main._repository is second
    finally:
        # Closes `second` (the current singleton) exactly once; `first` was
        # already closed above by the replace itself.
        configure_repository(None)


def test_configure_repository_none_resets_the_singleton_for_the_next_test() -> None:
    """After teardown, the module-global singleton must be exactly `None`
    -- the same starting point every test (via the autouse fixture) begins
    from, never a stale object left behind by whatever ran previously."""

    configure_repository(None)
    assert api_main._repository is None


def test_stale_repository_is_never_reused_after_its_directory_disappears(
    tmp_path: Path,
) -> None:
    """A repository whose backing tmp directory has since been deleted (the
    normal end-of-test cleanup) must never be silently resurrected/reused by
    a later, unrelated construction -- there is no path-keyed process-global
    cache to go stale."""

    doomed_root = tmp_path / "doomed"
    doomed = ProductRepository(db_url=f"sqlite:///{doomed_root / 'mockingbird.sqlite3'}")
    doomed.create_camera_source(_marker_source_payload("marker-in-doomed-repository"))
    doomed.close()

    shutil.rmtree(doomed_root)

    fresh = ProductRepository(db_url=f"sqlite:///{tmp_path / 'fresh' / 'mockingbird.sqlite3'}")
    try:
        assert "marker-in-doomed-repository" not in {s.name for s in fresh.list_sources()}
    finally:
        fresh.close()


def _marker_source_payload(name: str) -> CameraSourceCreate:
    return CameraSourceCreate(name=name)


# --- Part 6 (background-task race): drain_background_tasks lifecycle ---
#
# `test_camera_node.py`'s real `/api/camera-nodes/pair` tests are the
# concrete case this closes: a successful pairing fires a detached
# `asyncio.create_task(_refresh_camera_node_pairing_profiles(...))` that
# calls `get_repository()` again after its own first `await`. Left
# undrained, that task can still be sleeping when a test's own teardown
# resets the repository singleton to `None` -- so it wakes up and resolves
# the now-unconfigured default instead of the test's isolated repository.
# An instrumented whole-suite sweep (this milestone's own Part 1 trace)
# caught exactly this, live, in four pre-existing tests.


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_drain_background_tasks_waits_for_a_pending_task_to_finish() -> None:
    finished = False

    async def slow_task() -> None:
        nonlocal finished
        await asyncio.sleep(0.05)
        finished = True

    api_main._track_background_task(asyncio.create_task(slow_task()))
    assert finished is False

    await drain_background_tasks()

    assert finished is True


@pytest.mark.anyio
async def test_drain_background_tasks_removes_finished_tasks_from_the_pending_set() -> None:
    async def quick_task() -> None:
        return None

    task = asyncio.create_task(quick_task())
    api_main._track_background_task(task)

    await drain_background_tasks()

    assert task not in api_main._pending_background_tasks


@pytest.mark.anyio
async def test_drain_background_tasks_never_silently_swallows_a_failure() -> None:
    async def failing_task() -> None:
        raise UnsafeDefaultStorageAccessError("simulated: drained too late")

    api_main._track_background_task(asyncio.create_task(failing_task()))

    with pytest.raises(UnsafeDefaultStorageAccessError):
        await drain_background_tasks()
