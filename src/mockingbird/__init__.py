"""MockingBird package."""

__all__ = ["__version__"]

#: Development-checkout fallback only -- a real installed MockingBird (an
#: editable dev install via `pip install -e .`, or a real packaged release
#: wheel installed into the Windows bundle's embeddable Python by
#: `scripts/build_local_product.py`) always has proper `.dist-info`
#: metadata; `importlib.metadata` resolves it directly below. A raw,
#: uninstalled checkout importing `mockingbird` straight from `src/` --
#: never MockingBird's own supported dev or packaged-product path -- has no
#: such metadata, so this literal is the honest last-resort fallback for
#: that case only. Mirrors `mockingbird_node.__version__`'s identical
#: existing convention exactly. Keep in sync with `pyproject.toml`'s
#: `[project].version` by hand -- a regression test
#: (`tests/test_version_provenance.py`) enforces this.
#: Final Release Candidate Corrections v1: restored to "0.1.0" -- see
#: `pyproject.toml`'s own comment for the reasoning.
_DEV_CHECKOUT_FALLBACK_VERSION = "0.1.0"


def _resolve_version() -> str:
    """The installed MockingBird package version. Never raises."""

    from importlib import metadata

    try:
        return metadata.version("mockingbird")
    except metadata.PackageNotFoundError:
        return _DEV_CHECKOUT_FALLBACK_VERSION


__version__ = _resolve_version()
