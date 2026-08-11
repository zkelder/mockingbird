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
"""

from __future__ import annotations

import pytest

from mockingbird.api import main as api_main
from mockingbird.api.main import configure_repository
from mockingbird.repository.product_repository import ProductRepository


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
    """

    isolation_root = tmp_path_factory.mktemp("default_isolation")
    repository = ProductRepository(
        db_url=f"sqlite:///{isolation_root / 'mockingbird.sqlite3'}",
        media_root=isolation_root / "media",
    )
    configure_repository(repository)
    try:
        yield repository
    finally:
        if api_main._repository is repository:
            configure_repository(None)
        else:
            repository.close()
