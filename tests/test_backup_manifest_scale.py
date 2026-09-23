"""Performance / Scale / Stability Closure v1 -- backup at real media counts.

A backup archive's manifest carries one entry per retained media file, so
it grows with the library. `MAX_MANIFEST_BYTES` -- the guard that stops
`_read_manifest` reading an unbounded blob out of a possibly-hostile
archive -- was 1 MiB, which a legitimate manifest exceeds at roughly 6,800
media files (~154 bytes per entry once `json.dumps(..., indent=2)` has
formatted it).

That is about two months of ordinary use at this product's own measured
rate (four evidence frames per Visit, ~30 Visits/day for an established
feeder), and the consequence was not "an old backup cannot be read":
`create_backup` verifies the archive it has just written, so *no backup
could be made at all*, and because the pre-migration safety backup is a
hard gate on migrating, the same install could no longer be upgraded
either. Reproduced end to end against a 2,813-Visit / 11,244-media-asset
library before the fix (`backup_manifest_invalid`, migration refused).

These tests pin both halves: a real round trip at a media count past the
old limit, and the guard still rejecting a genuinely oversized manifest.
"""

from __future__ import annotations

import json
import zipfile

import pytest

from mockingbird.storage.backup import (
    MANIFEST_MEMBER,
    MAX_MANIFEST_BYTES,
    LocalBackupManager,
    LocalBackupValidationError,
)


# Comfortably past the old 1 MiB manifest limit (~6,800 entries) while
# staying fast enough for the suite: 9,000 tiny files.
_MEDIA_FILE_COUNT = 9_000


@pytest.fixture
def manager(tmp_path):
    media_root = tmp_path / "media"
    media_root.mkdir()
    (tmp_path / "data").mkdir()
    return LocalBackupManager(
        db_url=f"sqlite:///{tmp_path / 'data' / 'mockingbird.sqlite3'}",
        media_root=media_root,
        backup_root=tmp_path / "backups",
    )


def _seed_database(manager: LocalBackupManager) -> None:
    import sqlite3

    manager.database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(manager.database_path)
    connection.execute("CREATE TABLE IF NOT EXISTS mockingbird_schema (singleton_id INTEGER PRIMARY KEY, version INTEGER)")
    connection.execute("INSERT OR REPLACE INTO mockingbird_schema VALUES (1, 60)")
    connection.commit()
    connection.close()


def _seed_media(manager: LocalBackupManager, count: int) -> None:
    for index in range(count):
        # A few directories deep, like real evidence storage.
        directory = manager.media_root / f"perf/{index // 500:03d}"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"frame-{index:06d}.jpg").write_bytes(b"\xff\xd8\xff\xd9")


def test_a_backup_succeeds_past_the_old_manifest_limit(manager) -> None:
    _seed_database(manager)
    _seed_media(manager, _MEDIA_FILE_COUNT)

    verification = manager.create_backup(kind="manual")

    with zipfile.ZipFile(verification.backup.archive_path) as archive:
        manifest = json.loads(archive.read(MANIFEST_MEMBER))
    assert manifest["media_file_count"] == _MEDIA_FILE_COUNT
    # The very thing that used to fail: this manifest is bigger than the
    # old cap, and must still be readable.
    manifest_bytes = len(json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"))
    assert manifest_bytes > 1_048_576, (
        "fixture no longer exercises the defect -- its manifest is under the old 1 MiB cap"
    )
    assert manifest_bytes < MAX_MANIFEST_BYTES


def test_the_archive_it_just_wrote_verifies(manager) -> None:
    """`create_backup` verifies its own output; that must hold at scale."""

    _seed_database(manager)
    _seed_media(manager, _MEDIA_FILE_COUNT)

    verification = manager.create_backup(kind="manual")
    revalidated = manager.verify_archive(verification.backup.archive_path)
    assert revalidated.backup.media_file_count == _MEDIA_FILE_COUNT


def test_a_pre_migration_backup_succeeds_at_the_same_scale(manager) -> None:
    """The kind the upgrade path depends on -- the real blocker."""

    _seed_database(manager)
    _seed_media(manager, _MEDIA_FILE_COUNT)

    verification = manager.create_backup(kind="pre_migration")
    assert verification.backup.kind == "pre_migration"
    assert verification.backup.archive_path.exists()


def test_the_guard_still_rejects_an_oversized_manifest(manager, tmp_path) -> None:
    """Raising the cap must not remove the protection it exists for."""

    _seed_database(manager)
    _seed_media(manager, 4)
    verification = manager.create_backup(kind="manual")

    hostile = tmp_path / "hostile.mbbackup"
    with zipfile.ZipFile(verification.backup.archive_path) as source:
        with zipfile.ZipFile(hostile, mode="w", compression=zipfile.ZIP_STORED) as target:
            for info in source.infolist():
                if info.filename == MANIFEST_MEMBER:
                    continue
                target.writestr(info, source.read(info.filename))
            target.writestr(
                MANIFEST_MEMBER,
                b"x" * (MAX_MANIFEST_BYTES + 1),
                compress_type=zipfile.ZIP_STORED,
            )

    with pytest.raises(LocalBackupValidationError) as raised:
        manager.verify_archive(hostile)
    assert str(raised.value) == "backup_manifest_invalid"


def test_the_cap_covers_a_decade_of_ordinary_use() -> None:
    """Document, as an assertion, what the chosen bound actually buys."""

    bytes_per_entry = 154  # measured from a real manifest entry
    supported_files = MAX_MANIFEST_BYTES // bytes_per_entry
    # Four evidence frames per Visit, ~30 Visits/day for an established
    # feeder -- this repository's own measured rate.
    files_per_year = 4 * 30 * 365
    assert supported_files / files_per_year > 9, (
        f"cap supports only {supported_files:,} media files "
        f"({supported_files / files_per_year:.1f} years at the measured rate)"
    )
