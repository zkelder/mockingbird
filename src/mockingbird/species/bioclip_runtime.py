"""Packaged-runtime path resolution for the optional local BioCLIP adapter.

Mirrors `mockingbird.observation.engine_runtime`'s "packaged asset next to
this installed package" convention, which already solves exactly this
problem for the Observation Engine's MDv5 model bundle:
`scripts/build_local_product.py` copies the accepted BioCLIP model bundle
(model config, weights, frozen 14-species labels, precomputed embedding
cache -- docs/model-selection.md's "Supported local BioCLIP 2 artifact")
into `<installed package>/bioclip_runtime/` at build time, so a normal
packaged Windows install needs no `MOCKINGBIRD_BIOCLIP_*` environment
variable set by hand. Explicit environment variables remain fully honored
and are never required, for a developer or advanced user who wants a
different local bundle than the one that shipped.

This module never imports `bioclip_adapter`'s heavy optional runtime
(PIL/numpy/open_clip/torch) and never does anything beyond a simple
filesystem existence check -- it only answers "where should these three
paths come from," the same narrow, side-effect-free job
`engine_runtime.resolve_provider_config_path` does for the Observation
Engine's provider configuration.

Deliberately no third "development checkout convention" fallback the way
`engine_runtime.resolve_provider_config_path` has for the Observation
Engine (a `data/models/...` path resolved against `find_workspace_root()`).
That convention's own dev-fallback path does not exist in a normal
checkout, so it is a safe no-op there -- but the real local BioCLIP
evaluation bundle this project actually uses during development
(`data/models/bioclip-2/`) *does* exist on disk in this checkout.
Auto-discovering it here would silently change "no environment variables
set" behavior from today's honest "not configured" to "configured" for
every existing caller/test that relies on that contract (see
tests/test_review_identification.py and friends, which `monkeypatch.delenv`
the three variables to start from a known-clean state) -- a behavior
change this packaging/configuration-only milestone does not ask for and
must not cause. A bare development checkout keeps using the unchanged,
explicit `MOCKINGBIRD_BIOCLIP_*` environment variables exactly as before;
only an actual packaged build (which never ships inside `src/mockingbird/`
itself) gets the new automatic default.
"""

from __future__ import annotations

import os
from pathlib import Path

# Mirrors `mockingbird.observation.engine_runtime.PACKAGED_OBSERVATION_
# RUNTIME_DIRNAME` exactly. Also duplicated as a literal (the same
# established convention that module and `scripts/build_local_product.py`
# already use for `PACKAGED_OBSERVATION_RUNTIME_DIRNAME`) in
# `scripts/build_local_product.py` and `scripts/deploy_windows_dev.py`, so
# neither build/deploy tool needs `mockingbird` importable from the build
# host's ambient environment. Keep all three copies in sync.
PACKAGED_BIOCLIP_RUNTIME_DIRNAME = "bioclip_runtime"

# The three environment variables the optional BioCLIP shadow has always
# honored (see `product_repository.BIOCLIP_MODEL_PATH_ENV` and friends,
# and README.md's "Optional local species suggestions" section) --
# duplicated here as literals rather than imported from
# `mockingbird.repository.product_repository`, which already imports
# *from* `mockingbird.species`: importing the other way would create a
# layering cycle. Keep these three strings in sync with that module's own
# copies.
BIOCLIP_MODEL_PATH_ENV = "MOCKINGBIRD_BIOCLIP_MODEL_PATH"
BIOCLIP_LABELS_PATH_ENV = "MOCKINGBIRD_BIOCLIP_LABELS_PATH"
BIOCLIP_EMBEDDING_CACHE_PATH_ENV = "MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH"

# Fixed filenames within the packaged runtime root -- the same four files
# `scripts/build_local_product.py`'s `package_bioclip_runtime_assets`
# copies there from the accepted local bundle, and the same four names the
# existing local developer convention (`data/models/bioclip-2/`) already
# uses. Keep all four in sync with that function.
PACKAGED_BIOCLIP_MODEL_CONFIG_FILENAME = "open_clip_config.json"
PACKAGED_BIOCLIP_LABELS_FILENAME = "mockingbird-bird-candidates.txt"
PACKAGED_BIOCLIP_EMBEDDING_CACHE_FILENAME = "mockingbird-bird-candidates.npz"


def packaged_bioclip_runtime_root() -> Path:
    """Where a packaged MockingBird install ships its default BioCLIP model
    bundle -- populated by `scripts/build_local_product.py`, mirroring
    `engine_runtime.packaged_observation_runtime_root`'s own "packaged
    asset next to this installed package" convention exactly
    (`observation_runtime` there, `bioclip_runtime` here; both live at the
    installed `mockingbird` package's own root, sibling to this `species/`
    package). The model *directory itself* is this root: `open_clip_
    config.json` plus a safe weights file
    (`bioclip_adapter._SAFE_MODEL_WEIGHT_NAMES`) sit directly inside it,
    exactly like the existing `data/models/bioclip-2/` local developer
    convention -- no extra nesting.

    Resolved from *this module's own installed location*, never
    `os.getcwd()`, so it keeps resolving correctly after `runtime.py`'s
    `run_preflight()` changes the process working directory to the runtime
    home, and after restarting MockingBird from any other working
    directory.
    """

    return Path(__file__).resolve().parent.parent / PACKAGED_BIOCLIP_RUNTIME_DIRNAME


def _resolve_bioclip_path(
    *, override: str | Path | None, env_var: str, packaged_path: Path, packaged_marker: Path
) -> Path | None:
    """Shared precedence for one BioCLIP local artifact path:

    1. an explicit caller-supplied override (tests, a future setup flow);
    2. the environment variable this path has always honored (still
       honored, never required for a packaged install) -- returned exactly
       as given, unchanged from today's existing behavior;
    3. `packaged_path` (the packaged runtime root itself for the model
       *directory*, or one fixed file inside it for the labels/embedding-
       cache paths) -- only when `packaged_marker` genuinely exists as a
       file, never a guessed/nonexistent path (mirrors `engine_runtime.
       resolve_provider_config_path`'s own `packaged_candidate.is_file()`
       check for its packaged candidate). `packaged_marker` is what proves
       the packaged root is genuinely populated, not an empty/partial
       directory; it may be the same path as `packaged_path` (labels,
       embedding cache) or a different file inside the same directory
       (the model directory itself, proven populated by its config file).

    Returns `None` (never a guessed path) when nothing above resolves --
    `BioClipAdapterConfig`/`get_bioclip_status` already treat `None` as an
    honest "not configured" fact, exactly today's existing contract for a
    checkout or install with no BioCLIP artifacts anywhere.
    """

    if override is not None:
        return Path(override)
    configured = os.environ.get(env_var)
    if configured:
        return Path(configured)
    if packaged_marker.is_file():
        return packaged_path
    return None


def resolve_bioclip_model_dir(override: str | Path | None = None) -> Path | None:
    """The BioCLIP model *directory* (containing `open_clip_config.json`
    and a safe weights file) -- see `_resolve_bioclip_path`."""

    packaged_root = packaged_bioclip_runtime_root()
    return _resolve_bioclip_path(
        override=override,
        env_var=BIOCLIP_MODEL_PATH_ENV,
        packaged_path=packaged_root,
        packaged_marker=packaged_root / PACKAGED_BIOCLIP_MODEL_CONFIG_FILENAME,
    )


def resolve_bioclip_labels_path(override: str | Path | None = None) -> Path | None:
    """The frozen local/seasonal candidate-labels file -- see
    `_resolve_bioclip_path`."""

    candidate = packaged_bioclip_runtime_root() / PACKAGED_BIOCLIP_LABELS_FILENAME
    return _resolve_bioclip_path(
        override=override,
        env_var=BIOCLIP_LABELS_PATH_ENV,
        packaged_path=candidate,
        packaged_marker=candidate,
    )


def resolve_bioclip_embedding_cache_path(override: str | Path | None = None) -> Path | None:
    """The precomputed text-embedding cache matching the labels above --
    see `_resolve_bioclip_path`."""

    candidate = packaged_bioclip_runtime_root() / PACKAGED_BIOCLIP_EMBEDDING_CACHE_FILENAME
    return _resolve_bioclip_path(
        override=override,
        env_var=BIOCLIP_EMBEDDING_CACHE_PATH_ENV,
        packaged_path=candidate,
        packaged_marker=candidate,
    )
