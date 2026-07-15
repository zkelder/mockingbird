"""Verified local backup artifacts and rollback-safe file replacement."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
from typing import BinaryIO, Iterable
import uuid
import zipfile

from mockingbird.storage.database import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    sqlite_database_path,
)


BACKUP_FORMAT_VERSION = 1
DEFAULT_BACKUP_ROOT = Path("data/backups")
BACKUP_ROOT_ENV_VAR = "MOCKINGBIRD_BACKUP_ROOT"
BACKUP_EXTENSION = ".mbbackup"
MANIFEST_MEMBER = "manifest.json"
DATABASE_MEMBER = "database.sqlite3"
MAX_MANIFEST_BYTES = 1_048_576
COPY_CHUNK_BYTES = 1024 * 1024

_BACKUP_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class LocalBackupError(RuntimeError):
    """Base class for user-facing local backup failures."""


class LocalBackupUnsupportedError(LocalBackupError):
    """Raised when the configured storage layout cannot be backed up safely."""


class LocalBackupValidationError(LocalBackupError):
    """Raised when an archive fails structural, hash, or database checks."""


class LocalBackupNotFoundError(LocalBackupError):
    """Raised when a requested artifact is not in the local backup library."""


class LocalBackupConflictError(LocalBackupError):
    """Raised when an import would overwrite a different local artifact."""


class LocalBackupRestoreError(LocalBackupError):
    """Raised when staged files cannot safely replace the live installation."""


@dataclass(frozen=True)
class BackupSummaryData:
    id: str
    created_at: datetime
    kind: str
    database_schema_version: int
    database_size_bytes: int
    media_file_count: int
    media_size_bytes: int
    archive_size_bytes: int
    verification_status: str
    restore_compatible: bool
    archive_path: Path


@dataclass(frozen=True)
class BackupLibraryData:
    backups: list[BackupSummaryData]
    unreadable_backup_count: int


@dataclass(frozen=True)
class BackupVerificationData:
    backup: BackupSummaryData
    checked_at: datetime


@dataclass
class RestoreFileTransaction:
    """Holds rollback paths until a restored repository opens successfully."""

    database_path: Path
    media_root: Path
    staged_database: Path
    staged_media: Path
    rollback_database: Path
    rollback_media: Path
    rollback_sidecars: list[tuple[Path, Path]]
    had_database: bool
    had_media: bool
    completed: bool = False

    def commit(self) -> None:
        if self.completed:
            return
        _remove_generated_path(self.rollback_database, self.database_path.parent)
        _remove_generated_path(self.rollback_media, self.media_root.parent)
        for _live_path, rollback_path in self.rollback_sidecars:
            _remove_generated_path(rollback_path, self.database_path.parent)
        _remove_generated_path(self.staged_database, self.database_path.parent)
        _remove_generated_path(self.staged_media, self.media_root.parent)
        self.completed = True

    def rollback(self) -> None:
        if self.completed:
            return

        _remove_live_database_file(self.database_path)
        for suffix in ("-wal", "-shm"):
            _remove_live_database_file(Path(f"{self.database_path}{suffix}"))
        if self.had_database and self.rollback_database.exists():
            os.replace(self.rollback_database, self.database_path)

        _remove_managed_media_root(self.media_root)
        if self.had_media and self.rollback_media.exists():
            os.replace(self.rollback_media, self.media_root)

        for live_path, rollback_path in self.rollback_sidecars:
            if rollback_path.exists():
                os.replace(rollback_path, live_path)

        _remove_generated_path(self.staged_database, self.database_path.parent)
        _remove_generated_path(self.staged_media, self.media_root.parent)
        self.completed = True


def backup_root_from_env() -> Path:
    return Path(os.getenv(BACKUP_ROOT_ENV_VAR, str(DEFAULT_BACKUP_ROOT)))


def _resolved(path: Path) -> Path:
    return path.expanduser().resolve(strict=False)


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or _is_within(first, second) or _is_within(second, first)


def _validate_member_name(name: str) -> None:
    if not name or "\\" in name or name.endswith("/"):
        raise LocalBackupValidationError("backup_contains_unsafe_paths")
    path = PurePosixPath(name)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise LocalBackupValidationError("backup_contains_unsafe_paths")
    if path.as_posix() != name:
        raise LocalBackupValidationError("backup_contains_unsafe_paths")


def _require_dict(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LocalBackupValidationError(f"backup_manifest_invalid_{field}")
    return value


def _require_list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise LocalBackupValidationError(f"backup_manifest_invalid_{field}")
    return value


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise LocalBackupValidationError(f"backup_manifest_invalid_{field}")
    return value


def _require_nonnegative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise LocalBackupValidationError(f"backup_manifest_invalid_{field}")
    return value


def _parse_created_at(value: object) -> datetime:
    raw = _require_string(value, "created_at")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as error:
        raise LocalBackupValidationError("backup_manifest_invalid_created_at") from error
    if parsed.tzinfo is None:
        raise LocalBackupValidationError("backup_manifest_invalid_created_at")
    return parsed.astimezone(UTC)


def _hash_stream(source: BinaryIO, destination: BinaryIO | None = None) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = source.read(COPY_CHUNK_BYTES)
        if not chunk:
            break
        digest.update(chunk)
        size += len(chunk)
        if destination is not None:
            destination.write(chunk)
    return size, digest.hexdigest()


def _hash_file(path: Path) -> str:
    with path.open("rb") as source:
        return _hash_stream(source)[1]


def _validate_database_file(path: Path) -> int:
    try:
        connection = sqlite3.connect(path)
        try:
            integrity_rows = connection.execute("PRAGMA quick_check").fetchall()
            if integrity_rows != [("ok",)]:
                raise LocalBackupValidationError("backup_database_integrity_failed")
            row = connection.execute(
                "SELECT version FROM mockingbird_schema WHERE singleton_id = 1"
            ).fetchone()
        finally:
            connection.close()
    except LocalBackupValidationError:
        raise
    except sqlite3.Error as error:
        raise LocalBackupValidationError("backup_database_unreadable") from error

    if row is None or not isinstance(row[0], int):
        raise LocalBackupValidationError("backup_database_schema_record_missing")
    if row[0] != CURRENT_DATABASE_SCHEMA_VERSION:
        raise LocalBackupValidationError("backup_database_schema_incompatible")
    return int(row[0])


def _remove_generated_path(path: Path, allowed_parent: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    resolved_parent = _resolved(allowed_parent)
    resolved_path = _resolved(path)
    if resolved_path.parent != resolved_parent or not path.name.startswith(".mockingbird-restore-"):
        raise LocalBackupRestoreError("restore_cleanup_path_rejected")
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def _remove_live_database_file(path: Path) -> None:
    if path.exists() or path.is_symlink():
        if path.is_dir():
            raise LocalBackupRestoreError("restore_database_path_is_directory")
        path.unlink()


def _remove_managed_media_root(media_root: Path) -> None:
    if not media_root.exists() and not media_root.is_symlink():
        return
    resolved_root = _resolved(media_root)
    if resolved_root == Path(resolved_root.anchor) or resolved_root.parent == resolved_root:
        raise LocalBackupRestoreError("restore_media_root_rejected")
    if media_root.is_symlink() or not media_root.is_dir():
        raise LocalBackupRestoreError("restore_media_root_rejected")
    shutil.rmtree(media_root)


class LocalBackupManager:
    """Create and restore complete local SQLite + managed-media bundles."""

    def __init__(
        self,
        *,
        db_url: str,
        media_root: str | Path,
        backup_root: str | Path | None = None,
    ) -> None:
        try:
            database_path = sqlite_database_path(db_url)
        except ValueError as error:
            raise LocalBackupUnsupportedError(str(error)) from error

        self.database_path = _resolved(database_path)
        self.media_root = _resolved(Path(media_root))
        self.backup_root = _resolved(Path(backup_root) if backup_root else backup_root_from_env())
        self._validate_storage_layout()

    def _validate_storage_layout(self) -> None:
        if _is_within(self.database_path, self.media_root):
            raise LocalBackupUnsupportedError("database_cannot_be_inside_media_root")
        if _paths_overlap(self.media_root, self.backup_root):
            raise LocalBackupUnsupportedError("backup_root_cannot_overlap_media_root")
        if _is_within(self.database_path, self.backup_root):
            raise LocalBackupUnsupportedError("database_cannot_be_inside_backup_root")

    def _ensure_backup_root(self) -> None:
        self.backup_root.mkdir(parents=True, exist_ok=True)
        if self.backup_root.is_symlink() or not self.backup_root.is_dir():
            raise LocalBackupUnsupportedError("backup_root_is_not_a_directory")

    def _archive_path(self, backup_id: str) -> Path:
        if not _BACKUP_ID_PATTERN.fullmatch(backup_id):
            raise LocalBackupNotFoundError("backup_not_found")
        path = self.backup_root / f"{backup_id}{BACKUP_EXTENSION}"
        if not path.is_file() or path.is_symlink():
            raise LocalBackupNotFoundError("backup_not_found")
        return path

    def _discover_media_files(self) -> list[tuple[Path, str]]:
        if not self.media_root.exists():
            return []
        if self.media_root.is_symlink() or not self.media_root.is_dir():
            raise LocalBackupUnsupportedError("managed_media_root_is_not_a_directory")

        files: list[tuple[Path, str]] = []
        for path in sorted(self.media_root.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_symlink():
                raise LocalBackupUnsupportedError("managed_media_contains_symbolic_link")
            if path.is_dir():
                continue
            if not path.is_file():
                raise LocalBackupUnsupportedError("managed_media_contains_unsupported_file")
            resolved_path = path.resolve(strict=True)
            if not _is_within(resolved_path, self.media_root):
                raise LocalBackupUnsupportedError("managed_media_escapes_configured_root")
            relative_path = path.relative_to(self.media_root).as_posix()
            archive_name = f"media/{relative_path}"
            _validate_member_name(archive_name)
            files.append((path, archive_name))
        return files

    def _snapshot_database(self, destination: Path) -> int:
        if not self.database_path.is_file() or self.database_path.is_symlink():
            raise LocalBackupUnsupportedError("local_database_file_is_unavailable")
        try:
            source = sqlite3.connect(self.database_path)
            target = sqlite3.connect(destination)
            try:
                source.backup(target)
            finally:
                target.close()
                source.close()
        except sqlite3.Error as error:
            raise LocalBackupError("local_database_snapshot_failed") from error
        return _validate_database_file(destination)

    @staticmethod
    def _write_zip_member(
        archive: zipfile.ZipFile,
        member_name: str,
        source_path: Path,
    ) -> dict[str, object]:
        with source_path.open("rb") as source, archive.open(
            member_name,
            mode="w",
            force_zip64=True,
        ) as destination:
            size, digest = _hash_stream(source, destination)
        return {"path": member_name, "size_bytes": size, "sha256": digest}

    def create_backup(self, *, kind: str = "manual") -> BackupVerificationData:
        if kind not in {"manual", "pre_restore"}:
            raise ValueError("unsupported_backup_kind")
        self._ensure_backup_root()

        backup_id = uuid.uuid4().hex
        created_at = datetime.now(UTC)
        temporary_archive = self.backup_root / f".creating-{backup_id}{BACKUP_EXTENSION}"
        snapshot_path = self.backup_root / f".snapshot-{backup_id}.sqlite3"
        final_path = self.backup_root / f"{backup_id}{BACKUP_EXTENSION}"

        try:
            schema_version = self._snapshot_database(snapshot_path)
            media_files = self._discover_media_files()
            with zipfile.ZipFile(
                temporary_archive,
                mode="x",
                compression=zipfile.ZIP_STORED,
                allowZip64=True,
            ) as archive:
                database_entry = self._write_zip_member(
                    archive,
                    DATABASE_MEMBER,
                    snapshot_path,
                )
                media_entries = [
                    self._write_zip_member(archive, archive_name, source_path)
                    for source_path, archive_name in media_files
                ]
                manifest = {
                    "format_version": BACKUP_FORMAT_VERSION,
                    "backup_id": backup_id,
                    "created_at": created_at.isoformat(),
                    "kind": kind,
                    "source_layout": {
                        "database_path": str(self.database_path),
                        "media_root": str(self.media_root),
                    },
                    "database": {
                        **database_entry,
                        "schema_version": schema_version,
                    },
                    "media": media_entries,
                    "media_file_count": len(media_entries),
                    "media_size_bytes": sum(
                        int(entry["size_bytes"]) for entry in media_entries
                    ),
                }
                archive.writestr(
                    MANIFEST_MEMBER,
                    json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8"),
                    compress_type=zipfile.ZIP_STORED,
                )

            verification = self.verify_archive(temporary_archive)
            os.replace(temporary_archive, final_path)
            return replace(
                verification,
                backup=replace(
                    verification.backup,
                    archive_path=final_path,
                    archive_size_bytes=final_path.stat().st_size,
                ),
            )
        except (OSError, zipfile.BadZipFile) as error:
            raise LocalBackupError("local_backup_creation_failed") from error
        finally:
            if snapshot_path.exists():
                snapshot_path.unlink()
            if temporary_archive.exists():
                temporary_archive.unlink()

    def _read_manifest(self, archive_path: Path) -> tuple[dict[str, object], zipfile.ZipFile]:
        archive: zipfile.ZipFile | None = None
        try:
            archive = zipfile.ZipFile(archive_path, mode="r")
            info = archive.getinfo(MANIFEST_MEMBER)
            if info.file_size > MAX_MANIFEST_BYTES or info.compress_type != zipfile.ZIP_STORED:
                raise LocalBackupValidationError("backup_manifest_invalid")
            with archive.open(info) as source:
                raw = source.read(MAX_MANIFEST_BYTES + 1)
            if len(raw) > MAX_MANIFEST_BYTES:
                raise LocalBackupValidationError("backup_manifest_invalid")
            manifest = json.loads(raw.decode("utf-8"))
            return _require_dict(manifest, "root"), archive
        except LocalBackupValidationError:
            if archive is not None:
                archive.close()
            raise
        except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError, zipfile.BadZipFile) as error:
            if archive is not None:
                archive.close()
            raise LocalBackupValidationError("backup_manifest_unreadable") from error

    def _parse_manifest(
        self,
        manifest: dict[str, object],
        archive_path: Path,
        *,
        verification_status: str,
    ) -> tuple[BackupSummaryData, dict[str, object], list[dict[str, object]]]:
        if manifest.get("format_version") != BACKUP_FORMAT_VERSION:
            raise LocalBackupValidationError("backup_format_incompatible")

        backup_id = _require_string(manifest.get("backup_id"), "backup_id")
        if not _BACKUP_ID_PATTERN.fullmatch(backup_id):
            raise LocalBackupValidationError("backup_manifest_invalid_backup_id")
        created_at = _parse_created_at(manifest.get("created_at"))
        kind = _require_string(manifest.get("kind"), "kind")
        if kind not in {"manual", "pre_restore"}:
            raise LocalBackupValidationError("backup_manifest_invalid_kind")

        source_layout = _require_dict(manifest.get("source_layout"), "source_layout")
        source_database_path = _require_string(
            source_layout.get("database_path"), "source_database_path"
        )
        source_media_root = _require_string(source_layout.get("media_root"), "source_media_root")
        restore_compatible = (
            _resolved(Path(source_database_path)) == self.database_path
            and _resolved(Path(source_media_root)) == self.media_root
        )

        database = _require_dict(manifest.get("database"), "database")
        if database.get("path") != DATABASE_MEMBER:
            raise LocalBackupValidationError("backup_manifest_invalid_database_path")
        database_size = _require_nonnegative_int(
            database.get("size_bytes"), "database_size_bytes"
        )
        database_hash = _require_string(database.get("sha256"), "database_sha256")
        if not _SHA256_PATTERN.fullmatch(database_hash):
            raise LocalBackupValidationError("backup_manifest_invalid_database_sha256")
        schema_version = _require_nonnegative_int(
            database.get("schema_version"), "database_schema_version"
        )

        media_values = _require_list(manifest.get("media"), "media")
        media_entries: list[dict[str, object]] = []
        media_paths: set[str] = set()
        for index, value in enumerate(media_values):
            entry = _require_dict(value, f"media_{index}")
            path = _require_string(entry.get("path"), f"media_{index}_path")
            _validate_member_name(path)
            if not path.startswith("media/") or path in media_paths:
                raise LocalBackupValidationError("backup_manifest_invalid_media_path")
            media_paths.add(path)
            size = _require_nonnegative_int(entry.get("size_bytes"), f"media_{index}_size")
            digest = _require_string(entry.get("sha256"), f"media_{index}_sha256")
            if not _SHA256_PATTERN.fullmatch(digest):
                raise LocalBackupValidationError("backup_manifest_invalid_media_sha256")
            media_entries.append({"path": path, "size_bytes": size, "sha256": digest})

        declared_count = _require_nonnegative_int(
            manifest.get("media_file_count"), "media_file_count"
        )
        declared_size = _require_nonnegative_int(
            manifest.get("media_size_bytes"), "media_size_bytes"
        )
        if declared_count != len(media_entries):
            raise LocalBackupValidationError("backup_manifest_media_count_mismatch")
        if declared_size != sum(int(entry["size_bytes"]) for entry in media_entries):
            raise LocalBackupValidationError("backup_manifest_media_size_mismatch")

        summary = BackupSummaryData(
            id=backup_id,
            created_at=created_at,
            kind=kind,
            database_schema_version=schema_version,
            database_size_bytes=database_size,
            media_file_count=declared_count,
            media_size_bytes=declared_size,
            archive_size_bytes=archive_path.stat().st_size,
            verification_status=verification_status,
            restore_compatible=restore_compatible,
            archive_path=archive_path,
        )
        return summary, database, media_entries

    @staticmethod
    def _validate_archive_members(
        archive: zipfile.ZipFile,
        database: dict[str, object],
        media_entries: Iterable[dict[str, object]],
    ) -> dict[str, zipfile.ZipInfo]:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if len(names) != len(set(names)):
            raise LocalBackupValidationError("backup_contains_duplicate_paths")
        for info in infos:
            _validate_member_name(info.filename)
            if info.compress_type != zipfile.ZIP_STORED or info.flag_bits & 0x1:
                raise LocalBackupValidationError("backup_member_encoding_unsupported")

        declared_entries = [database, *media_entries]
        expected_names = {MANIFEST_MEMBER, *(str(entry["path"]) for entry in declared_entries)}
        if set(names) != expected_names:
            raise LocalBackupValidationError("backup_member_list_mismatch")
        info_by_name = {info.filename: info for info in infos}
        for entry in declared_entries:
            info = info_by_name[str(entry["path"])]
            if info.file_size != int(entry["size_bytes"]):
                raise LocalBackupValidationError("backup_member_size_mismatch")
        return info_by_name

    def verify_archive(self, archive_path: str | Path) -> BackupVerificationData:
        self._ensure_backup_root()
        path = _resolved(Path(archive_path))
        temporary_database = self.backup_root / f".verify-{uuid.uuid4().hex}.sqlite3"
        archive: zipfile.ZipFile | None = None
        try:
            manifest, archive = self._read_manifest(path)
            summary, database, media_entries = self._parse_manifest(
                manifest,
                path,
                verification_status="verified",
            )
            info_by_name = self._validate_archive_members(archive, database, media_entries)

            with archive.open(info_by_name[DATABASE_MEMBER]) as source, temporary_database.open(
                "wb"
            ) as destination:
                database_size, database_hash = _hash_stream(source, destination)
            if database_size != int(database["size_bytes"]) or database_hash != database["sha256"]:
                raise LocalBackupValidationError("backup_database_hash_mismatch")

            schema_version = _validate_database_file(temporary_database)
            if schema_version != summary.database_schema_version:
                raise LocalBackupValidationError("backup_database_schema_mismatch")

            for entry in media_entries:
                with archive.open(info_by_name[str(entry["path"])]) as source:
                    size, digest = _hash_stream(source)
                if size != int(entry["size_bytes"]) or digest != entry["sha256"]:
                    raise LocalBackupValidationError("backup_media_hash_mismatch")

            return BackupVerificationData(backup=summary, checked_at=datetime.now(UTC))
        except LocalBackupValidationError:
            raise
        except (OSError, RuntimeError, zipfile.BadZipFile) as error:
            raise LocalBackupValidationError("backup_verification_failed") from error
        finally:
            if archive is not None:
                archive.close()
            if temporary_database.exists():
                temporary_database.unlink()

    def list_backups(self) -> BackupLibraryData:
        self._ensure_backup_root()
        backups: list[BackupSummaryData] = []
        unreadable_count = 0
        for path in self.backup_root.glob(f"*{BACKUP_EXTENSION}"):
            if not path.is_file() or path.is_symlink():
                unreadable_count += 1
                continue
            archive: zipfile.ZipFile | None = None
            try:
                manifest, archive = self._read_manifest(path)
                summary, _database, _media = self._parse_manifest(
                    manifest,
                    path,
                    verification_status="not_checked",
                )
                if path.stem != summary.id:
                    raise LocalBackupValidationError("backup_filename_identity_mismatch")
                backups.append(summary)
            except LocalBackupValidationError:
                unreadable_count += 1
            finally:
                if archive is not None:
                    archive.close()
        backups.sort(key=lambda item: item.created_at, reverse=True)
        return BackupLibraryData(backups=backups, unreadable_backup_count=unreadable_count)

    def verify_backup(self, backup_id: str) -> BackupVerificationData:
        verification = self.verify_archive(self._archive_path(backup_id))
        if verification.backup.id != backup_id:
            raise LocalBackupValidationError("backup_filename_identity_mismatch")
        return verification

    def download_path(self, backup_id: str) -> Path:
        verification = self.verify_backup(backup_id)
        return verification.backup.archive_path

    def import_backup(self, source: BinaryIO) -> BackupVerificationData:
        self._ensure_backup_root()
        temporary_path = self.backup_root / f".import-{uuid.uuid4().hex}{BACKUP_EXTENSION}"
        try:
            with temporary_path.open("xb") as destination:
                _hash_stream(source, destination)
            verification = self.verify_archive(temporary_path)
            final_path = self.backup_root / f"{verification.backup.id}{BACKUP_EXTENSION}"
            if final_path.exists():
                if _hash_file(final_path) == _hash_file(temporary_path):
                    return self.verify_archive(final_path)
                raise LocalBackupConflictError("backup_id_already_exists")
            os.replace(temporary_path, final_path)
            return replace(
                verification,
                backup=replace(
                    verification.backup,
                    archive_path=final_path,
                    archive_size_bytes=final_path.stat().st_size,
                ),
            )
        except LocalBackupError:
            raise
        except OSError as error:
            raise LocalBackupError("backup_import_failed") from error
        finally:
            if temporary_path.exists():
                temporary_path.unlink()

    def assert_restore_compatible(self, verification: BackupVerificationData) -> None:
        if not verification.backup.restore_compatible:
            raise LocalBackupConflictError("backup_storage_layout_mismatch")

    def _extract_staged_restore(
        self,
        verification: BackupVerificationData,
    ) -> tuple[Path, Path]:
        token = uuid.uuid4().hex
        staged_database = self.database_path.parent / f".mockingbird-restore-{token}-database-staged"
        staged_media = self.media_root.parent / f".mockingbird-restore-{token}-media-staged"
        staged_database.parent.mkdir(parents=True, exist_ok=True)
        staged_media.parent.mkdir(parents=True, exist_ok=True)
        staged_media.mkdir()

        archive: zipfile.ZipFile | None = None
        try:
            manifest, archive = self._read_manifest(verification.backup.archive_path)
            _summary, database, media_entries = self._parse_manifest(
                manifest,
                verification.backup.archive_path,
                verification_status="verified",
            )
            info_by_name = self._validate_archive_members(archive, database, media_entries)
            with archive.open(info_by_name[DATABASE_MEMBER]) as source, staged_database.open(
                "xb"
            ) as destination:
                size, digest = _hash_stream(source, destination)
            if size != int(database["size_bytes"]) or digest != database["sha256"]:
                raise LocalBackupValidationError("backup_database_hash_mismatch")
            _validate_database_file(staged_database)

            for entry in media_entries:
                relative_path = PurePosixPath(str(entry["path"])).relative_to("media")
                destination_path = staged_media.joinpath(*relative_path.parts)
                if not _is_within(_resolved(destination_path), _resolved(staged_media)):
                    raise LocalBackupValidationError("backup_contains_unsafe_paths")
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info_by_name[str(entry["path"])]) as source, destination_path.open(
                    "xb"
                ) as destination:
                    size, digest = _hash_stream(source, destination)
                if size != int(entry["size_bytes"]) or digest != entry["sha256"]:
                    raise LocalBackupValidationError("backup_media_hash_mismatch")
            return staged_database, staged_media
        except Exception:
            _remove_generated_path(staged_database, self.database_path.parent)
            _remove_generated_path(staged_media, self.media_root.parent)
            raise
        finally:
            if archive is not None:
                archive.close()

    def replace_live_files(
        self,
        verification: BackupVerificationData,
    ) -> RestoreFileTransaction:
        """Stage a verified artifact and replace live files, retaining rollback paths."""

        self.assert_restore_compatible(verification)
        staged_database, staged_media = self._extract_staged_restore(verification)
        token = uuid.uuid4().hex
        rollback_database = (
            self.database_path.parent / f".mockingbird-restore-{token}-database-rollback"
        )
        rollback_media = self.media_root.parent / f".mockingbird-restore-{token}-media-rollback"
        rollback_sidecars = [
            (
                Path(f"{self.database_path}{suffix}"),
                self.database_path.parent
                / f".mockingbird-restore-{token}-{suffix.removeprefix('-')}-rollback",
            )
            for suffix in ("-wal", "-shm")
        ]
        transaction = RestoreFileTransaction(
            database_path=self.database_path,
            media_root=self.media_root,
            staged_database=staged_database,
            staged_media=staged_media,
            rollback_database=rollback_database,
            rollback_media=rollback_media,
            rollback_sidecars=rollback_sidecars,
            had_database=self.database_path.exists(),
            had_media=self.media_root.exists(),
        )

        try:
            if transaction.had_database:
                os.replace(self.database_path, rollback_database)
            for live_path, rollback_path in rollback_sidecars:
                if live_path.exists():
                    os.replace(live_path, rollback_path)
            if transaction.had_media:
                if self.media_root.is_symlink() or not self.media_root.is_dir():
                    raise LocalBackupRestoreError("restore_media_root_rejected")
                os.replace(self.media_root, rollback_media)
            os.replace(staged_database, self.database_path)
            os.replace(staged_media, self.media_root)
            return transaction
        except Exception as error:
            try:
                transaction.rollback()
            except Exception as rollback_error:
                raise LocalBackupRestoreError("restore_and_rollback_failed") from rollback_error
            if isinstance(error, LocalBackupError):
                raise
            raise LocalBackupRestoreError("restore_file_replacement_failed") from error
