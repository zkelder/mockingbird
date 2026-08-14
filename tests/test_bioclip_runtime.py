"""`mockingbird.species.bioclip_runtime` -- packaged-runtime path resolution
for the optional BioCLIP species-suggestion adapter.

Mirrors `tests/test_engine_runtime.py`'s own "Packaged-runtime configuration
resolution (no env var required)" test shapes for the Observation Engine's
identical `resolve_provider_config_path` convention. Entirely hermetic: no
real network, no real ~1.6 GB model file, except the one real-bundle proof
below, which is skipped (never failed) when this build host does not have
the real local BioCLIP evaluation bundle this project actually uses during
development.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mockingbird.repository.product_repository import ProductRepository
from mockingbird.species import bioclip_runtime
from mockingbird.species.bioclip_adapter import build_bioclip_config, get_bioclip_status
from mockingbird.species.bioclip_runtime import (
    resolve_bioclip_embedding_cache_path,
    resolve_bioclip_labels_path,
    resolve_bioclip_model_dir,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_BIOCLIP_BUNDLE_SOURCE = REPO_ROOT / "data" / "models" / "bioclip-2"

ENV_VARS = (
    bioclip_runtime.BIOCLIP_MODEL_PATH_ENV,
    bioclip_runtime.BIOCLIP_LABELS_PATH_ENV,
    bioclip_runtime.BIOCLIP_EMBEDDING_CACHE_PATH_ENV,
)


@pytest.fixture(autouse=True)
def _clean_bioclip_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts from a known-clean state -- no BioCLIP environment
    variable set, matching the existing convention already used by
    tests/test_review_identification.py and friends."""

    for env_var in ENV_VARS:
        monkeypatch.delenv(env_var, raising=False)


# --- No configuration anywhere: honest None, never a guess ------------------


def test_resolves_to_none_with_no_env_var_and_no_packaged_root(monkeypatch: pytest.MonkeyPatch) -> None:
    """A bare development checkout (or a packaged install with no BioCLIP
    bundle supplied at build time) reports `None` for all three paths --
    the existing, unchanged "not configured" contract
    `BioClipAdapterConfig`/`get_bioclip_status` already rely on."""

    monkeypatch.setattr(bioclip_runtime, "packaged_bioclip_runtime_root", lambda: Path("/no/such/packaged/root"))

    assert resolve_bioclip_model_dir() is None
    assert resolve_bioclip_labels_path() is None
    assert resolve_bioclip_embedding_cache_path() is None


def test_never_auto_discovers_the_real_local_development_bundle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Deliberately different from `engine_runtime.resolve_provider_config_
    path`'s own development-checkout fallback: this module must never
    resolve `data/models/bioclip-2/` on its own just because this specific
    checkout happens to have one sitting on disk -- see the module's own
    docstring for why (existing tests/dev behavior with no environment
    variable set must stay "not configured", unchanged)."""

    monkeypatch.setattr(bioclip_runtime, "packaged_bioclip_runtime_root", lambda: Path("/no/such/packaged/root"))

    assert resolve_bioclip_model_dir() is None
    assert resolve_bioclip_labels_path() is None
    assert resolve_bioclip_embedding_cache_path() is None


# --- Packaged root: a normal packaged install needs no environment variable -


def test_resolves_model_dir_from_packaged_root_when_config_file_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    packaged_root = tmp_path / "bioclip_runtime"
    packaged_root.mkdir()
    (packaged_root / bioclip_runtime.PACKAGED_BIOCLIP_MODEL_CONFIG_FILENAME).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bioclip_runtime, "packaged_bioclip_runtime_root", lambda: packaged_root)

    assert resolve_bioclip_model_dir() == packaged_root


def test_model_dir_ignores_packaged_root_missing_its_config_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """An empty/partially-populated packaged root (a build that failed to
    package a bundle, or a stray directory) is never mistaken for a real
    one -- checked by the presence of its one specific expected file, never
    the bare directory's existence."""

    packaged_root = tmp_path / "bioclip_runtime"
    packaged_root.mkdir()
    monkeypatch.setattr(bioclip_runtime, "packaged_bioclip_runtime_root", lambda: packaged_root)

    assert resolve_bioclip_model_dir() is None


def test_resolves_labels_and_embedding_cache_from_packaged_root(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    packaged_root = tmp_path / "bioclip_runtime"
    packaged_root.mkdir()
    labels_path = packaged_root / bioclip_runtime.PACKAGED_BIOCLIP_LABELS_FILENAME
    cache_path = packaged_root / bioclip_runtime.PACKAGED_BIOCLIP_EMBEDDING_CACHE_FILENAME
    labels_path.write_text("House Finch\n", encoding="utf-8")
    cache_path.write_bytes(b"fake-cache-bytes")
    monkeypatch.setattr(bioclip_runtime, "packaged_bioclip_runtime_root", lambda: packaged_root)

    assert resolve_bioclip_labels_path() == labels_path
    assert resolve_bioclip_embedding_cache_path() == cache_path


def test_packaged_bioclip_runtime_root_is_sibling_of_observation_runtime() -> None:
    """Mirrors `engine_runtime.packaged_observation_runtime_root`'s exact
    "packaged asset next to this installed package" convention -- both
    resolve to a directory directly under the installed `mockingbird`
    package root, sibling to `species/`."""

    root = bioclip_runtime.packaged_bioclip_runtime_root()
    assert root.name == bioclip_runtime.PACKAGED_BIOCLIP_RUNTIME_DIRNAME
    assert root.parent.name == "mockingbird"


# --- Environment variable: still honored, never required --------------------


def test_env_var_still_wins_over_packaged_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    packaged_root = tmp_path / "bioclip_runtime"
    packaged_root.mkdir()
    (packaged_root / bioclip_runtime.PACKAGED_BIOCLIP_MODEL_CONFIG_FILENAME).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bioclip_runtime, "packaged_bioclip_runtime_root", lambda: packaged_root)

    monkeypatch.setenv(bioclip_runtime.BIOCLIP_MODEL_PATH_ENV, "/custom/model/dir")
    assert resolve_bioclip_model_dir() == Path("/custom/model/dir")


def test_explicit_override_wins_over_everything(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    packaged_root = tmp_path / "bioclip_runtime"
    packaged_root.mkdir()
    (packaged_root / bioclip_runtime.PACKAGED_BIOCLIP_MODEL_CONFIG_FILENAME).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bioclip_runtime, "packaged_bioclip_runtime_root", lambda: packaged_root)
    monkeypatch.setenv(bioclip_runtime.BIOCLIP_MODEL_PATH_ENV, "/custom/model/dir")

    assert resolve_bioclip_model_dir(Path("/explicit/dir")) == Path("/explicit/dir")


def test_resolution_independent_of_cwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Restarting MockingBird from a different working directory (exactly
    what `runtime.py`'s `run_preflight` does) must not change which
    packaged BioCLIP root resolves -- resolved from this module's own
    installed location, never `os.getcwd()`."""

    packaged_root = tmp_path / "bioclip_runtime"
    packaged_root.mkdir()
    (packaged_root / bioclip_runtime.PACKAGED_BIOCLIP_MODEL_CONFIG_FILENAME).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bioclip_runtime, "packaged_bioclip_runtime_root", lambda: packaged_root)

    elsewhere = tmp_path / "some" / "other" / "working" / "directory"
    elsewhere.mkdir(parents=True)
    monkeypatch.chdir(elsewhere)

    assert resolve_bioclip_model_dir() == packaged_root


# --- Real bundle, when available on this build host -------------------------


@pytest.mark.skipif(
    not REAL_BIOCLIP_BUNDLE_SOURCE.is_dir(), reason="real local BioCLIP evaluation bundle not present on this build host",
)
def test_real_local_bundle_resolves_as_available_through_the_packaged_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Not a fixture: points the packaged-root resolver directly at this
    repository's own real local BioCLIP bundle (`data/models/bioclip-2/`,
    the exact same real, already-proven-working artifact
    `scripts/build_local_product.py`'s own `DEFAULT_BIOCLIP_BUNDLE_SOURCE`
    packages from) and proves the full resolution chain plus the existing,
    unmodified adapter status check together report it as genuinely
    available -- the real "normal app startup with BioCLIP configured"
    proof, skipped (never failed) on a host without the real bundle."""

    monkeypatch.setattr(bioclip_runtime, "packaged_bioclip_runtime_root", lambda: REAL_BIOCLIP_BUNDLE_SOURCE)

    config = build_bioclip_config(
        model_dir=resolve_bioclip_model_dir(),
        labels_path=resolve_bioclip_labels_path(),
        embedding_cache_path=resolve_bioclip_embedding_cache_path(),
        device="cpu",
    )
    assert config.model_dir == REAL_BIOCLIP_BUNDLE_SOURCE
    assert config.labels_path is not None
    assert config.embedding_cache_path is not None

    status = get_bioclip_status(config)
    assert status.status == "available", status.detail
    assert status.configured is True


# --- Normal app startup, through the real ProductRepository/model-adapter --
# surface (never the low-level resolver functions directly) -- "normal app
# startup without BioCLIP" / "normal app startup with BioCLIP configured".


def _repository(tmp_path: Path) -> ProductRepository:
    return ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")


def test_normal_app_startup_without_bioclip_reports_not_configured(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A normal app startup with no BioCLIP bundle packaged and no
    environment variable set must list `bioclip_2` as `not_configured` --
    never crash, never silently claim availability -- exactly the existing,
    unchanged degradation contract."""

    monkeypatch.setattr(bioclip_runtime, "packaged_bioclip_runtime_root", lambda: tmp_path / "no-such-packaged-root")

    repository = _repository(tmp_path)
    adapter = repository.get_model_adapter("bioclip_2")

    assert adapter is not None
    assert adapter.status.value == "not_configured"
    assert adapter.configuration_status is not None
    assert adapter.configuration_status.can_run is False


@pytest.mark.skipif(
    not REAL_BIOCLIP_BUNDLE_SOURCE.is_dir(), reason="real local BioCLIP evaluation bundle not present on this build host",
)
def test_normal_app_startup_with_bioclip_configured_reports_available(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The real "normal app startup with BioCLIP configured" proof: with
    the packaged root pointed at this repository's own real local bundle
    (standing in for what a real packaged deploy would have placed there)
    and zero environment variables set, the real `ProductRepository`
    surface a running app actually serves reports `bioclip_2` as available
    -- proving the full chain (packaged-root resolution -> `_bioclip_
    config` -> `get_bioclip_status` -> `ModelAdapter`) together, not just
    the low-level resolver in isolation."""

    monkeypatch.setattr(bioclip_runtime, "packaged_bioclip_runtime_root", lambda: REAL_BIOCLIP_BUNDLE_SOURCE)

    repository = _repository(tmp_path)
    adapter = repository.get_model_adapter("bioclip_2")

    assert adapter is not None
    assert adapter.status.value == "available", adapter.notes
    assert adapter.configuration_status is not None
    assert adapter.configuration_status.can_run is True
