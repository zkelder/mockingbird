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


@pytest.mark.parametrize(
    ("total_bytes", "free_bytes", "expected_tier"),
    [
        # A 100 GB disk: the 5%/15%/1% ratio floors (5/15/1 GB) each exceed
        # their absolute-byte counterparts (1 GB/5 GB/200 MB), so ratio
        # comparisons are what actually decide the tier here.
        (100_000_000_000, 20_000_000_000, "healthy"),  # 20% free, above every floor
        (100_000_000_000, 8_000_000_000, "getting_low"),  # 8% free: below 15%, above 5%
        (100_000_000_000, 3_000_000_000, "action_recommended"),  # 3% free: below 5%, above 1%
        (100_000_000_000, 500_000_000, "critical"),  # 0.5% free: below the 1% ratio floor
        # A 1 TB disk: ratio floors (10/50/150 GB) are now far larger than
        # the absolute-byte floors, so a small absolute free amount reads
        # as critical purely via ratio even though it is well above 200 MB.
        (1_000_000_000_000, 5_000_000_000, "critical"),  # 5 GB free is > 200MB, but only 0.5% of 1 TB
        # A 10 GB disk: 1% of it (100 MB) is *below* the 200 MB absolute
        # floor, so the absolute floor is what decides here instead: 150 MB
        # free is 1.5% (above the 1% ratio floor) but still under 200 MB.
        (10_000_000_000, 150_000_000, "critical"),
        (0, 0, "healthy"),  # unknown total (probe failed): never fabricates alarm from zero/zero
    ],
)
def test_storage_health_tier_ladder(total_bytes: int, free_bytes: int, expected_tier: str) -> None:
    """Appliance / Storage / Privacy / Recovery v1, Phase C: the graduated
    healthy/getting_low/action_recommended/critical ladder -- `is_low_space`
    above stays exactly the `action_recommended`-or-worse boundary it
    always was; this proves the two new tiers around it."""

    status = LocalStorageDiskStatus(total_bytes=total_bytes, free_bytes=free_bytes, is_writable=True)

    assert status.storage_health_tier == expected_tier
    # Backward-compatible: `is_low_space` still means exactly
    # action_recommended-or-worse, never affected by the new tiers.
    assert status.is_low_space == (expected_tier in {"action_recommended", "critical"})


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
