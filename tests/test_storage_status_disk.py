"""Host-disk writable/low-space status -- distinct from managed-media
accounting, which `test_storage_retention*.py` already covers. See
docs/local-product-packaging-design.md.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from mockingbird.repository import product_repository as repository_module
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.database import LocalStorageDiskStatus, probe_local_storage_disk


def test_probe_reports_a_normal_writable_directory(tmp_path: Path) -> None:
    status = probe_local_storage_disk(tmp_path)

    assert status.is_writable is True
    assert status.total_bytes > 0
    assert status.free_bytes > 0
    assert status.is_low_space is False


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="permission bits do not block root")
def test_probe_reports_not_writable_when_permissions_deny_write(tmp_path: Path) -> None:
    locked_directory = tmp_path / "locked"
    locked_directory.mkdir()
    locked_directory.chmod(0o500)  # read + execute only

    try:
        status = probe_local_storage_disk(locked_directory)
        assert status.is_writable is False
    finally:
        locked_directory.chmod(0o700)  # restore so tmp_path cleanup can remove it


def test_probe_never_leaves_its_sentinel_file_behind(tmp_path: Path) -> None:
    probe_local_storage_disk(tmp_path)

    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    ("total_bytes", "free_bytes", "expected_low_space"),
    [
        (100_000_000_000, 50_000_000_000, False),  # plenty free, well above both thresholds
        (100_000_000_000, 500_000_000, True),  # below the absolute 1 GB floor
        (100_000_000_000, 4_000_000_000, True),  # above 1 GB free, but below the 5% ratio floor
        (0, 0, False),  # unknown total (probe failed): never claims low space from zero/zero
    ],
)
def test_is_low_space_threshold(total_bytes: int, free_bytes: int, expected_low_space: bool) -> None:
    status = LocalStorageDiskStatus(total_bytes=total_bytes, free_bytes=free_bytes, is_writable=True)

    assert status.is_low_space is expected_low_space


def test_storage_summary_surfaces_disk_fields_and_low_space_warning(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    monkeypatch.setattr(
        repository_module,
        "probe_local_storage_disk",
        lambda _directory: LocalStorageDiskStatus(
            total_bytes=100_000_000_000, free_bytes=200_000_000, is_writable=True
        ),
    )

    summary = repository.storage_summary()

    assert summary.is_writable is True
    assert summary.disk_total_bytes == 100_000_000_000
    assert summary.disk_free_bytes == 200_000_000
    assert summary.storage_warning is not None
    assert "low" in summary.storage_warning.lower()


def test_storage_summary_reports_unwritable_storage_before_low_space(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    monkeypatch.setattr(
        repository_module,
        "probe_local_storage_disk",
        lambda _directory: LocalStorageDiskStatus(
            total_bytes=100_000_000_000, free_bytes=100_000_000, is_writable=False
        ),
    )

    summary = repository.storage_summary()

    assert summary.is_writable is False
    assert summary.storage_warning is not None
    assert "writable" in summary.storage_warning.lower()
