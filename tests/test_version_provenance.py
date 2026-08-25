"""Release Engineering Foundation v1: a real, confirmed gap (see the
milestone report) was four independently hand-typed `"0.1.0"` literals --
`pyproject.toml`, `mockingbird.__version__`'s dev-checkout fallback,
`mockingbird_node.__version__`'s dev-checkout fallback, and the FastAPI
`app` object's own decorative `version=` string -- with nothing catching
drift if one were bumped without the others. `mockingbird.__version__` and
the FastAPI `app.version` now resolve live from installed package metadata
(never independently hardcoded at the consumption site); this file is the
regression guard for the two dev-checkout-only fallback literals that must
still be kept in sync by hand.
"""

from __future__ import annotations

import tomllib

import mockingbird
import mockingbird_node
from mockingbird.web_app import find_workspace_root


def _pyproject_version() -> str:
    workspace_root = find_workspace_root()
    assert workspace_root is not None, "could not locate this checkout's own pyproject.toml"
    with (workspace_root / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return data["project"]["version"]


def test_pyproject_version_matches_the_mockingbird_dev_checkout_fallback() -> None:
    assert mockingbird._DEV_CHECKOUT_FALLBACK_VERSION == _pyproject_version()


def test_pyproject_version_matches_the_camera_node_dev_checkout_fallback() -> None:
    assert mockingbird_node.__version__ == _pyproject_version()


def test_mockingbird_dunder_version_resolves_from_real_installed_package_metadata() -> None:
    """This checkout is pip-installed (editable or real) in every supported
    dev/test/packaged-product path, so `__version__` should already reflect
    genuine installed-package metadata, not silently fall through to the
    dev-checkout literal -- proving the resolution order actually works,
    not only that the two texts happen to agree above."""

    from importlib import metadata

    assert mockingbird.__version__ == metadata.version("mockingbird")


def test_fastapi_app_version_matches_mockingbird_dunder_version() -> None:
    """The FastAPI `app` object's own `version=` (OpenAPI docs metadata
    only -- `main.py`'s own comment notes the real `X-MockingBird-Api-
    Version` response header uses `APP_VERSION` directly) must never drift
    from the single resolved version every other surface reports."""

    from mockingbird.api.main import app

    assert app.version == mockingbird.__version__
