"""Regression coverage for the Stage-2 checkpoint atomic-staging fix.

``pytorch_lightning``'s checkpoint writer (``_atomic_save``) stages every
write through an ``fsspec`` local-filesystem transaction. Inside that
transaction, ``fsspec.implementations.local.LocalFileOpener._open`` calls a
bare ``tempfile.mkstemp()`` -- no ``dir=`` -- so the staging file lands
wherever ``tempfile.gettempdir()`` resolves, independent of the checkpoint's
real destination directory. If that default resolves to a different
filesystem/mount than the checkpoint directory (for example a Windows drive
mounted into WSL2 at ``/mnt/c`` versus the repository's native ext4 root),
the commit step's ``shutil.move`` cannot use a same-filesystem ``os.rename``
and instead falls back to a real copy of the whole checkpoint -- which is
what produced the epoch-0 ``checkpoint_0.ckpt`` recovery this fix follows.

These tests exercise ``scripts/train_wildlife_stage2_rfdetr.py``'s
``_stage_checkpoint_tempdir`` in isolation, without importing torch/rfdetr,
mirroring the established ``importlib``-based pattern other tests use to
unit-test a `scripts/*.py` module's pure-Python helpers directly (see
``tests/test_zone_diagnostic.py``).
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile

import pytest


def _training_module():
    path = Path("scripts/train_wildlife_stage2_rfdetr.py")
    spec = importlib.util.spec_from_file_location("train_wildlife_stage2_rfdetr", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def _restore_process_wide_tempdir_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """``_stage_checkpoint_tempdir`` mutates process-global state on purpose.

    Snapshot it through ``monkeypatch`` before any test runs it, so whatever
    the function under test does to ``tempfile.tempdir``/``TMPDIR``/``TEMP``/
    ``TMP`` is undone afterwards -- monkeypatch restores the value observed
    at this call, regardless of how many times production code reassigns it
    in between. Without this, one test here could leave every later test in
    the suite staging its *own* temp files under a deleted ``tmp_path``.
    """

    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    for key in ("TMPDIR", "TEMP", "TMP"):
        if key in os.environ:
            monkeypatch.setenv(key, os.environ[key])
        else:
            monkeypatch.delenv(key, raising=False)


def test_stage_checkpoint_tempdir_points_tempfile_at_the_output_directory(
    tmp_path: Path,
) -> None:
    module = _training_module()
    output = tmp_path / "experiments" / "rfdetr-small-stage2-v0.2"

    staging = module._stage_checkpoint_tempdir(output)

    assert staging == output / ".checkpoint-staging"
    assert staging.is_dir()
    assert tempfile.gettempdir() == str(staging)
    assert os.environ["TMPDIR"] == str(staging)
    assert os.environ["TEMP"] == str(staging)
    assert os.environ["TMP"] == str(staging)


def test_stage_checkpoint_tempdir_makes_the_checkpoint_commit_a_real_rename(
    tmp_path: Path,
) -> None:
    """Reproduce fsspec's ``LocalFileOpener`` non-autocommit write+commit.

    This is the actual failure mode, not just a proxy for it: stage a file
    with a bare ``tempfile.mkstemp()`` (exactly what fsspec calls, with no
    ``dir=``) and then commit it with ``os.rename`` (what ``shutil.move``
    uses whenever it does not have to fall back to a cross-filesystem copy).
    Before this fix, ``tempfile.mkstemp()`` could resolve outside ``output``
    entirely; a cross-filesystem ``os.rename`` there would raise ``OSError``
    (errno ``EXDEV``) instead of completing silently.
    """

    module = _training_module()
    output = tmp_path / "experiments" / "rfdetr-small-stage2-v0.2"
    module._stage_checkpoint_tempdir(output)

    descriptor, staged_name = tempfile.mkstemp()
    os.close(descriptor)
    staged_path = Path(staged_name)
    staged_path.write_bytes(b"fake checkpoint payload")

    assert staged_path.parent == output / ".checkpoint-staging"
    assert staged_path.stat().st_dev == output.stat().st_dev

    destination = output / "checkpoint_0.ckpt"
    os.rename(staged_path, destination)  # raises OSError(EXDEV) if not same-device

    assert destination.read_bytes() == b"fake checkpoint payload"
    assert not staged_path.exists()


def test_stage_checkpoint_tempdir_is_idempotent_across_repeated_checkpoints(
    tmp_path: Path,
) -> None:
    """A 10+ epoch run calls this once per checkpoint write; it must not
    fail or drift on repeated calls against the same output directory."""

    module = _training_module()
    output = tmp_path / "experiments" / "rfdetr-small-stage2-v0.2"

    first = module._stage_checkpoint_tempdir(output)
    second = module._stage_checkpoint_tempdir(output)

    assert first == second
    assert tempfile.gettempdir() == str(first)


def test_stage_checkpoint_tempdir_fails_closed_if_staging_is_ever_cross_device(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The same-device check is structurally unreachable for a plain child
    directory today; prove the fail-closed branch itself still works so it
    is not silent dead code if that ever changes."""

    module = _training_module()
    output = tmp_path / "experiments" / "rfdetr-small-stage2-v0.2"
    real_stat = os.stat

    class _SpoofedStat:
        def __init__(self, st_dev: int) -> None:
            self.st_dev = st_dev

    def spoofed_stat(path, *args, **kwargs):
        result = real_stat(path, *args, **kwargs)
        if Path(path) == output:
            return _SpoofedStat(st_dev=result.st_dev + 1)
        return result

    monkeypatch.setattr(module.os, "stat", spoofed_stat)

    with pytest.raises(
        module.WildlifeTrainingError,
        match="checkpoint_staging_dir_not_same_filesystem",
    ):
        module._stage_checkpoint_tempdir(output)
