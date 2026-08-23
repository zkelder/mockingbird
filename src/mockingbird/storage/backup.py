"""Verified local backup artifacts and rollback-safe file replacement."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import shutil
import sqlite3
from typing import Any, BinaryIO, Iterable
import uuid
import zipfile

from mockingbird.storage.database import (
    database_schema_version_is_compatible,
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

# Appliance / Storage / Privacy / Recovery v1: every temporary-name prefix
# this file writes under before an atomic `os.replace`/cleanup finishes the
# real operation (`create_backup`, `import_backup`, `verify_archive`,
# `create_restore_plan`). Their own `finally` blocks remove them on any
# raised exception, but a hard process kill (power loss, OOM kill, SIGKILL)
# skips `finally` entirely, leaving an orphan behind. Two distinct problems
# this one list closes: (1) the two `{BACKUP_EXTENSION}`-suffixed patterns
# would otherwise be picked up by `list_backups`'s own glob (`Path.glob`,
# unlike the top-level `glob.glob()` function, does not exclude dotfiles),
# fail to parse, and count as "unreadable" forever with no way to tell a
# temporary orphan apart from a genuinely corrupted backup; (2) all five
# patterns are real, if usually small, disk space that nothing ever
# reclaimed before `cleanup_orphaned_temporary_artifacts`. See
# docs/appliance-storage-privacy-recovery-v1-contract.md, "Backup
# diagnosability."
# Appliance / Storage / Privacy / Recovery v1, Phase G/O: written by
# `replace_live_files` before its first `os.replace` and removed after its
# last one succeeds (or after a raised exception's own rollback completes) --
# see `LocalBackupManager.detect_interrupted_restore`'s docstring for why
# this exists: a raised Python exception mid-swap is already well-handled
# by `RestoreFileTransaction.rollback()`, but a hard process kill (not an
# exception) between two of the swap's several `os.replace` calls skips
# that rollback entirely, and nothing before this sentinel could ever tell
# a live installation apart from one left mid-restore.
RESTORE_SENTINEL_FILENAME = ".mockingbird-restore-in-progress.json"

_TEMPORARY_ARTIFACT_GLOBS = (
    f".creating-*{BACKUP_EXTENSION}",
    f".import-*{BACKUP_EXTENSION}",
    ".snapshot-*.sqlite3",
    ".verify-*.sqlite3",
    ".restore-plan-*.sqlite3",
)
# Generous on purpose: even a very large real backup/import completes in
# well under a minute on ordinary hardware (see this file's own `create_
# backup`/`import_backup`), so anything still present after this long was
# never going to finish -- an orphan, not a slow-but-live operation this
# cleanup could race.
DEFAULT_ORPHANED_ARTIFACT_MIN_AGE_SECONDS = 3600.0

_BACKUP_ID_PATTERN = re.compile(r"^[0-9a-f]{32}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_WINDOWS_DRIVE_PATTERN = re.compile(r"^[A-Za-z]:")
_VIRTUAL_REFERENCE_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")

_ENTITY_COUNT_TABLES = {
    "sources": "camera_sources",
    "streams": "streams",
    "media_assets": "media_assets",
    "events": "events",
    "visits": "visits",
    "review_labels": "review_labels",
    "species_suggestions": "species_suggestions",
    "bioclip_attempts": "bioclip_identification_attempts",
    "dataset_exports": "dataset_exports",
    "monitoring_exposure_intervals": "monitoring_exposure_intervals",
}
_EXTERNAL_REFERENCE_CONFIG_KEYS = {
    "device_url",
    "ffmpeg_binary_path",
    "folder_path",
    "live_stream_url",
    "local_camera_device",
    "url",
    "workspace_path",
}
_PATH_LIKE_CONFIG_KEY_PARTS = ("path", "root", "directory", "folder", "workspace")


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


@dataclass(frozen=True)
class _PortablePath:
    style: str
    drive: str
    absolute: bool
    parts: tuple[str, ...]


@dataclass(frozen=True)
class ManagedPathRebindData:
    table: str
    record_id: str
    column: str
    source_value: str
    target_value: str
    archive_relative_path: str


@dataclass(frozen=True)
class RestorePlanData:
    backup_id: str
    dry_run: bool
    confirmed: bool
    rebind_managed_storage: bool
    restore_allowed: bool
    database_schema_version: int
    source_database_path: str
    source_media_root: str
    target_database_path: str
    target_media_root: str
    managed_database_reference_count: int
    media_archive_entry_count: int
    external_paths_preserved: tuple[str, ...]
    warnings: tuple[str, ...]
    unsafe_paths: tuple[str, ...]
    collisions: tuple[str, ...]
    expected_entity_counts: dict[str, int]
    path_rebinds: tuple[ManagedPathRebindData, ...]


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


def _is_virtual_reference(value: str) -> bool:
    return bool(_VIRTUAL_REFERENCE_PATTERN.match(value))


def _portable_path(value: str, *, fallback_style: str | None = None) -> _PortablePath:
    if not value or "\x00" in value:
        raise LocalBackupValidationError("restore_managed_path_invalid")

    use_windows = bool(_WINDOWS_DRIVE_PATTERN.match(value) or "\\" in value)
    if fallback_style == "windows" and not value.startswith("/"):
        use_windows = True

    if use_windows:
        raw = value.replace("/", "\\")
        if any(part in {".", ".."} for part in raw.split("\\")):
            raise LocalBackupValidationError("restore_managed_path_traversal")
        path = PureWindowsPath(raw)
        if path.root and not path.drive:
            raise LocalBackupValidationError("restore_managed_path_absolute_child")
        if path.drive and not path.is_absolute():
            raise LocalBackupValidationError("restore_managed_path_drive_relative")
        parts = tuple(part for part in path.parts if part != path.anchor)
        return _PortablePath(
            style="windows",
            drive=path.drive.casefold(),
            absolute=path.is_absolute(),
            parts=parts,
        )

    if any(part in {".", ".."} for part in value.split("/")):
        raise LocalBackupValidationError("restore_managed_path_traversal")
    path = PurePosixPath(value)
    parts = tuple(part for part in path.parts if part != path.anchor)
    return _PortablePath(
        style="posix",
        drive="",
        absolute=path.is_absolute(),
        parts=parts,
    )


def _path_parts_equal(
    first: Iterable[str], second: Iterable[str], *, style: str
) -> bool:
    first_parts = tuple(first)
    second_parts = tuple(second)
    if style == "windows":
        return tuple(part.casefold() for part in first_parts) == tuple(
            part.casefold() for part in second_parts
        )
    return first_parts == second_parts


def _storage_paths_equal(source: str, target: str) -> bool:
    try:
        source_path = _portable_path(source)
        target_path = _portable_path(target)
    except LocalBackupValidationError:
        return False
    return (
        source_path.style == target_path.style
        and source_path.drive == target_path.drive
        and source_path.absolute == target_path.absolute
        and _path_parts_equal(
            source_path.parts,
            target_path.parts,
            style=source_path.style,
        )
    )


def _archive_relative_for_managed_path(
    value: str,
    *,
    source_media_root: str,
    archive_relative_paths: Iterable[str],
) -> str:
    source_root = _portable_path(source_media_root)
    if not source_root.absolute:
        raise LocalBackupValidationError("restore_source_media_root_not_absolute")
    stored = _portable_path(value, fallback_style=source_root.style)

    candidates: list[str] = []
    for relative_path in archive_relative_paths:
        relative_parts = PurePosixPath(relative_path).parts
        if stored.absolute:
            if stored.style != source_root.style or stored.drive != source_root.drive:
                continue
            if len(stored.parts) < len(source_root.parts):
                continue
            if not _path_parts_equal(
                stored.parts[: len(source_root.parts)],
                source_root.parts,
                style=source_root.style,
            ):
                continue
            tail = stored.parts[len(source_root.parts) :]
            if _path_parts_equal(tail, relative_parts, style=source_root.style):
                candidates.append(relative_path)
            continue

        if _path_parts_equal(stored.parts, relative_parts, style=source_root.style):
            candidates.append(relative_path)
            continue
        if len(stored.parts) <= len(relative_parts):
            continue
        tail = stored.parts[-len(relative_parts) :]
        prefix = stored.parts[: -len(relative_parts)]
        if not _path_parts_equal(tail, relative_parts, style=source_root.style):
            continue
        if len(prefix) <= len(source_root.parts) and _path_parts_equal(
            prefix,
            source_root.parts[-len(prefix) :],
            style=source_root.style,
        ):
            candidates.append(relative_path)

    if len(candidates) != 1:
        raise LocalBackupValidationError("restore_managed_path_not_in_archive")
    return candidates[0]


def _database_entity_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }
    missing = set(_ENTITY_COUNT_TABLES.values()) - tables
    if missing:
        raise LocalBackupValidationError("restore_database_entity_tables_missing")
    return {
        label: int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for label, table in _ENTITY_COUNT_TABLES.items()
    }


def _database_external_path_fields(
    connection: sqlite3.Connection,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    preserved: set[str] = set()
    unsafe: set[str] = set()
    rows = connection.execute(
        "SELECT source_id, provider_key, config_json "
        "FROM source_provider_configurations"
    ).fetchall()
    for source_id, provider_key, raw_config in rows:
        try:
            config = json.loads(raw_config)
        except (TypeError, json.JSONDecodeError):
            unsafe.add(f"source_provider_configurations.{source_id}.config_json")
            continue
        if not isinstance(config, dict):
            unsafe.add(f"source_provider_configurations.{source_id}.config_json")
            continue
        for key, value in config.items():
            if not isinstance(key, str) or not isinstance(value, str) or not value:
                continue
            field = f"source_provider_configurations.{provider_key}.{key}"
            if key in _EXTERNAL_REFERENCE_CONFIG_KEYS:
                preserved.add(field)
            elif any(part in key.casefold() for part in _PATH_LIKE_CONFIG_KEY_PARTS):
                unsafe.add(field)
    return tuple(sorted(preserved)), tuple(sorted(unsafe))


def _path_has_symlink_component(path: Path) -> bool:
    candidate = path.expanduser().absolute()
    for component in (candidate, *candidate.parents):
        if component.exists() and component.is_symlink():
            return True
    return False


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


def _is_temporary_backup_artifact_name(name: str) -> bool:
    return any(Path(name).match(pattern) for pattern in _TEMPORARY_ARTIFACT_GLOBS)


def _atomic_write_text(path: Path, text: str) -> None:
    """`O_CREAT`/temp-file + `fsync` + `os.replace` -- this codebase's own
    established atomic-write idiom (see `camera_node_transport_ledger.
    _atomic_write_json`'s identical shape), duplicated rather than shared
    across modules per this codebase's existing convention for small,
    self-contained primitives."""

    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


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
    if not database_schema_version_is_compatible(row[0]):
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

        self.configured_database_path = database_path.expanduser().absolute()
        self.database_path = _resolved(self.configured_database_path)
        self.configured_media_root = Path(media_root).expanduser().absolute()
        self.media_root = _resolved(self.configured_media_root)
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

    def _verified_marker_path(self, backup_id: str) -> Path:
        return self.backup_root / f"{backup_id}.verified.json"

    def _write_verified_marker(self, backup_id: str, *, verified_at: datetime) -> None:
        """Record that `backup_id` passed full hash/schema verification at
        `verified_at` -- written once at the end of `create_backup`/
        `import_backup`/`verify_backup`, each of which has *just* run the
        real, heavier `verify_archive` (temp-database extraction, full
        media hash re-check). `list_backups` reads this back cheaply (one
        small file, no re-hashing) instead of hardcoding "not checked" for
        a backup that was, in fact, checked -- see docs/appliance-storage-
        privacy-recovery-v1-contract.md, "Backup diagnosability."

        Deliberately scoped: this records "verification passed as of this
        timestamp," not a live, continuously-enforced tamper-detection
        guarantee -- if the archive's bytes changed after this was written
        (a manual edit outside MockingBird, filesystem corruption), the
        marker does not know that; a user who suspects that can always run
        the real "Verify" action again, which rewrites this file fresh.
        Best-effort: a write failure here must never fail the backup/verify
        operation that produced this fact in the first place."""

        try:
            _atomic_write_text(
                self._verified_marker_path(backup_id),
                json.dumps({"verified_at": verified_at.isoformat()}),
            )
        except OSError:
            pass

    def _read_verified_at(self, backup_id: str) -> datetime | None:
        # A tolerant, direct parse of this module's own marker format (not
        # `_parse_created_at`, which is deliberately strict for untrusted
        # manifest input and raises `LocalBackupValidationError` --
        # inappropriate here, where a malformed/missing marker should just
        # mean "not known to be verified," never a hard failure).
        try:
            raw = json.loads(self._verified_marker_path(backup_id).read_text(encoding="utf-8"))
            parsed = datetime.fromisoformat(raw["verified_at"])
        except (OSError, ValueError, KeyError, TypeError):
            return None
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)

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
            _storage_paths_equal(source_database_path, str(self.database_path))
            and _storage_paths_equal(source_media_root, str(self.media_root))
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

            checked_at = datetime.now(UTC)
            # Appliance / Storage / Privacy / Recovery v1: this is the one
            # place every caller (create/import/explicit-verify/download)
            # funnels through after a real, full hash/schema verification
            # just passed -- regardless of which physical path/filename
            # `archive_path` was (a still-temporary `.creating-*`/`.import-*`
            # file during creation, or an already-final `<id>.mbbackup`),
            # `summary.id` is resolved from the manifest itself, so the
            # marker always lands under the backup's real, final identity.
            # See `_write_verified_marker`'s own docstring for scope.
            self._write_verified_marker(summary.id, verified_at=checked_at)
            return BackupVerificationData(backup=summary, checked_at=checked_at)
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
            if _is_temporary_backup_artifact_name(path.name):
                # A known in-progress-or-orphaned temporary name, never a
                # real backup -- excluded from both lists rather than
                # counted as "unreadable" (which would otherwise read as a
                # corrupted backup forever; see `cleanup_orphaned_temporary_
                # artifacts`, which is what actually reclaims these).
                continue
            if not path.is_file() or path.is_symlink():
                unreadable_count += 1
                continue
            archive: zipfile.ZipFile | None = None
            try:
                manifest, archive = self._read_manifest(path)
                # Appliance / Storage / Privacy / Recovery v1: a cheap,
                # no-re-hashing read of whether this backup has *ever*
                # passed a real verification (`_write_verified_marker`,
                # written by `verify_archive`) -- "not_checked" now means
                # what it says, rather than being hardcoded regardless of
                # this backup's real history. Still never re-hashes on
                # every list call, matching Doctor's own disclosed "prefer
                # the cheap check" precedent.
                verification_status = (
                    "verified" if self._read_verified_at(path.stem) is not None else "not_checked"
                )
                summary, _database, _media = self._parse_manifest(
                    manifest,
                    path,
                    verification_status=verification_status,
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

    def cleanup_orphaned_temporary_artifacts(
        self, *, min_age_seconds: float = DEFAULT_ORPHANED_ARTIFACT_MIN_AGE_SECONDS
    ) -> int:
        """Remove `.creating-*`/`.import-*`/`.snapshot-*` files left behind
        by a hard process kill mid-backup/import -- see this file's own
        `_TEMPORARY_ARTIFACT_GLOBS` docstring for why these can exist at
        all. Age-gated so this can never race a genuinely in-progress
        `create_backup`/`import_backup` call on another thread: only a file
        older than `min_age_seconds` (default one hour, far longer than any
        real operation takes) is ever removed. Safe to call repeatedly and
        safe to call when nothing needs cleaning -- returns the count
        actually removed. Never touches a real, correctly-named backup
        (`_is_temporary_backup_artifact_name` only ever matches the
        temporary prefixes above)."""

        if not self.backup_root.is_dir():
            return 0
        now = datetime.now(UTC).timestamp()
        removed = 0
        for pattern in _TEMPORARY_ARTIFACT_GLOBS:
            for path in self.backup_root.glob(pattern):
                try:
                    if path.is_symlink() or not path.is_file():
                        continue
                    if (now - path.stat().st_mtime) < min_age_seconds:
                        continue
                    path.unlink(missing_ok=True)
                    removed += 1
                except OSError:
                    continue
        return removed

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

    def create_restore_plan(
        self,
        verification: BackupVerificationData,
        *,
        rebind_managed_storage: bool = False,
    ) -> RestorePlanData:
        """Inspect a verified artifact without changing active product storage."""

        current = self.verify_archive(verification.backup.archive_path)
        if current.backup.id != verification.backup.id:
            raise LocalBackupValidationError("backup_identity_changed")
        if not current.backup.restore_compatible and not rebind_managed_storage:
            raise LocalBackupConflictError("backup_storage_layout_mismatch")

        temporary_database = (
            self.backup_root / f".restore-plan-{uuid.uuid4().hex}.sqlite3"
        )
        archive: zipfile.ZipFile | None = None
        try:
            manifest, archive = self._read_manifest(current.backup.archive_path)
            summary, database, media_entries = self._parse_manifest(
                manifest,
                current.backup.archive_path,
                verification_status="verified",
            )
            info_by_name = self._validate_archive_members(
                archive, database, media_entries
            )
            source_layout = _require_dict(
                manifest.get("source_layout"), "source_layout"
            )
            source_database_path = _require_string(
                source_layout.get("database_path"),
                "source_database_path",
            )
            source_media_root = _require_string(
                source_layout.get("media_root"),
                "source_media_root",
            )
            with (
                archive.open(info_by_name[DATABASE_MEMBER]) as source,
                temporary_database.open("xb") as destination,
            ):
                size, digest = _hash_stream(source, destination)
            if size != int(database["size_bytes"]) or digest != database["sha256"]:
                raise LocalBackupValidationError("backup_database_hash_mismatch")
            _validate_database_file(temporary_database)

            with sqlite3.connect(temporary_database) as connection:
                entity_counts = _database_entity_counts(connection)
                external_paths, unknown_external_paths = _database_external_path_fields(
                    connection
                )
                path_rebinds, unsafe_paths, collisions = (
                    self._plan_managed_path_rebinds(
                        connection,
                        source_database_path=source_database_path,
                        source_media_root=source_media_root,
                        media_entries=media_entries,
                        enabled=(
                            rebind_managed_storage and not summary.restore_compatible
                        ),
                    )
                )

            warnings: list[str] = []
            if rebind_managed_storage and not summary.restore_compatible:
                warnings.append("managed_storage_layout_will_be_rebound")
                unsafe_paths.extend(unknown_external_paths)
            if external_paths:
                warnings.append("external_provider_paths_will_be_preserved")
            if self.database_path.exists() or self.media_root.exists():
                warnings.append("existing_target_storage_will_be_replaced_atomically")

            return RestorePlanData(
                backup_id=summary.id,
                dry_run=True,
                confirmed=False,
                rebind_managed_storage=rebind_managed_storage,
                restore_allowed=not unsafe_paths and not collisions,
                database_schema_version=summary.database_schema_version,
                source_database_path=source_database_path,
                source_media_root=source_media_root,
                target_database_path=str(self.database_path),
                target_media_root=str(self.media_root),
                managed_database_reference_count=len(path_rebinds),
                media_archive_entry_count=len(media_entries),
                external_paths_preserved=external_paths,
                warnings=tuple(warnings),
                unsafe_paths=tuple(sorted(set(unsafe_paths))),
                collisions=tuple(sorted(set(collisions))),
                expected_entity_counts=entity_counts,
                path_rebinds=tuple(path_rebinds),
            )
        finally:
            if archive is not None:
                archive.close()
            if temporary_database.exists():
                temporary_database.unlink()

    def _plan_managed_path_rebinds(
        self,
        connection: sqlite3.Connection,
        *,
        source_database_path: str,
        source_media_root: str,
        media_entries: list[dict[str, object]],
        enabled: bool,
    ) -> tuple[list[ManagedPathRebindData], list[str], list[str]]:
        if not enabled:
            return [], [], []

        unsafe: list[str] = []
        collisions: list[str] = []
        rebinds: list[ManagedPathRebindData] = []
        try:
            source_database = _portable_path(source_database_path)
            if not source_database.absolute:
                unsafe.append("manifest.source_layout.database_path")
        except LocalBackupValidationError:
            unsafe.append("manifest.source_layout.database_path")

        if _path_has_symlink_component(self.configured_database_path.parent):
            unsafe.append("target.database_path_symlink")
        if _path_has_symlink_component(self.configured_media_root):
            unsafe.append("target.media_root_symlink")

        archive_relative_paths = [
            PurePosixPath(str(entry["path"])).relative_to("media").as_posix()
            for entry in media_entries
        ]
        target_by_key: dict[str, str] = {}
        for relative_path in archive_relative_paths:
            target = self.media_root.joinpath(*PurePosixPath(relative_path).parts)
            resolved_target = _resolved(target)
            if not _is_within(resolved_target, self.media_root):
                unsafe.append(f"archive.media.{relative_path}")
                continue
            portable_target = _portable_path(str(resolved_target))
            key_parts = portable_target.parts
            key = "/".join(
                part.casefold() if portable_target.style == "windows" else part
                for part in key_parts
            )
            previous = target_by_key.get(key)
            if previous is not None and previous != relative_path:
                collisions.extend((previous, relative_path))
            else:
                target_by_key[key] = relative_path

        media_target_by_archive: dict[str, str] = {}
        media_rows = connection.execute(
            "SELECT id, local_path FROM media_assets ORDER BY id"
        ).fetchall()
        for media_id, local_path in media_rows:
            field = f"media_assets.{media_id}.local_path"
            try:
                relative_path = _archive_relative_for_managed_path(
                    str(local_path),
                    source_media_root=source_media_root,
                    archive_relative_paths=archive_relative_paths,
                )
            except LocalBackupValidationError:
                unsafe.append(field)
                continue
            target = _resolved(
                self.media_root.joinpath(*PurePosixPath(relative_path).parts)
            )
            if not _is_within(target, self.media_root):
                unsafe.append(field)
                continue
            target_value = str(target)
            media_target_by_archive[relative_path] = target_value
            rebinds.append(
                ManagedPathRebindData(
                    table="media_assets",
                    record_id=str(media_id),
                    column="local_path",
                    source_value=str(local_path),
                    target_value=target_value,
                    archive_relative_path=relative_path,
                )
            )

        visit_rows = connection.execute(
            "SELECT id, representative_media_path FROM visits "
            "WHERE representative_media_path IS NOT NULL ORDER BY id"
        ).fetchall()
        for visit_id, media_path in visit_rows:
            value = str(media_path)
            if _is_virtual_reference(value):
                continue
            field = f"visits.{visit_id}.representative_media_path"
            try:
                relative_path = _archive_relative_for_managed_path(
                    value,
                    source_media_root=source_media_root,
                    archive_relative_paths=archive_relative_paths,
                )
            except LocalBackupValidationError:
                unsafe.append(field)
                continue
            target_value = media_target_by_archive.get(relative_path)
            if target_value is None:
                unsafe.append(field)
                continue
            rebinds.append(
                ManagedPathRebindData(
                    table="visits",
                    record_id=str(visit_id),
                    column="representative_media_path",
                    source_value=value,
                    target_value=target_value,
                    archive_relative_path=relative_path,
                )
            )
        return rebinds, unsafe, collisions

    def _rebind_staged_database(
        self,
        staged_database: Path,
        staged_media: Path,
        plan: RestorePlanData,
        media_entries: list[dict[str, object]],
    ) -> None:
        if not plan.restore_allowed:
            raise LocalBackupValidationError("restore_managed_storage_rebind_rejected")

        with sqlite3.connect(staged_database) as connection:
            before_counts = _database_entity_counts(connection)
            before_external = connection.execute(
                "SELECT source_id, provider_key, config_json "
                "FROM source_provider_configurations ORDER BY source_id"
            ).fetchall()
            try:
                connection.execute("BEGIN IMMEDIATE")
                for item in plan.path_rebinds:
                    if (item.table, item.column) not in {
                        ("media_assets", "local_path"),
                        ("visits", "representative_media_path"),
                    }:
                        raise LocalBackupValidationError(
                            "restore_managed_path_classification_invalid"
                        )
                    result = connection.execute(
                        f'UPDATE "{item.table}" SET "{item.column}" = ? '
                        f'WHERE id = ? AND "{item.column}" = ?',
                        (item.target_value, item.record_id, item.source_value),
                    )
                    if result.rowcount != 1:
                        raise LocalBackupValidationError(
                            "restore_managed_path_identity_changed"
                        )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

            after_counts = _database_entity_counts(connection)
            after_external = connection.execute(
                "SELECT source_id, provider_key, config_json "
                "FROM source_provider_configurations ORDER BY source_id"
            ).fetchall()
            if (
                before_counts != plan.expected_entity_counts
                or after_counts != before_counts
            ):
                raise LocalBackupValidationError("restore_entity_counts_changed")
            if after_external != before_external:
                raise LocalBackupValidationError("restore_external_paths_changed")
            if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
                raise LocalBackupValidationError("backup_database_integrity_failed")
            if connection.execute("PRAGMA foreign_key_check").fetchall():
                raise LocalBackupValidationError("restore_database_foreign_keys_failed")

            for item in plan.path_rebinds:
                row = connection.execute(
                    f'SELECT "{item.column}" FROM "{item.table}" WHERE id = ?',
                    (item.record_id,),
                ).fetchone()
                if row is None or row[0] != item.target_value:
                    raise LocalBackupValidationError(
                        "restore_managed_path_rebind_incomplete"
                    )

        entries_by_relative = {
            PurePosixPath(str(entry["path"])).relative_to("media").as_posix(): entry
            for entry in media_entries
        }
        for relative_path, entry in entries_by_relative.items():
            staged_path = staged_media.joinpath(*PurePosixPath(relative_path).parts)
            if not staged_path.is_file() or staged_path.is_symlink():
                raise LocalBackupValidationError("restore_staged_media_missing")
            if staged_path.stat().st_size != int(entry["size_bytes"]):
                raise LocalBackupValidationError("backup_media_hash_mismatch")
            if _hash_file(staged_path) != entry["sha256"]:
                raise LocalBackupValidationError("backup_media_hash_mismatch")

        _validate_database_file(staged_database)
    def assert_restore_compatible(self, verification: BackupVerificationData) -> None:
        if not verification.backup.restore_compatible:
            raise LocalBackupConflictError("backup_storage_layout_mismatch")

    def _extract_staged_restore(
        self,
        verification: BackupVerificationData,
        plan: RestorePlanData | None = None,
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
            if plan is not None and plan.rebind_managed_storage:
                self._rebind_staged_database(staged_database, staged_media, plan, media_entries)
            return staged_database, staged_media
        except Exception:
            _remove_generated_path(staged_database, self.database_path.parent)
            _remove_generated_path(staged_media, self.media_root.parent)
            raise
        finally:
            if archive is not None:
                archive.close()

    def _restore_sentinel_path(self) -> Path:
        return self.database_path.parent / RESTORE_SENTINEL_FILENAME

    def detect_interrupted_restore(self) -> dict[str, Any] | None:
        """Read-only, side-effect-free: is there a restore sentinel left
        behind by a hard process kill mid-`replace_live_files`? Safe to call
        from Doctor (no repository, no mutation) or from product startup.
        Returns the sentinel's own recorded facts (`backup_id`, `started_at`,
        rollback paths) or `None` when no restore is (or was left) in
        progress -- the overwhelmingly common case."""

        try:
            return json.loads(self._restore_sentinel_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def replace_live_files(
        self,
        verification: BackupVerificationData,
        *,
        rebind_managed_storage: bool = False,
        plan: RestorePlanData | None = None,
    ) -> RestoreFileTransaction:
        """Stage a verified artifact and replace live files, retaining rollback paths."""

        if rebind_managed_storage:
            selected_plan = plan or self.create_restore_plan(
                verification,
                rebind_managed_storage=True,
            )
            if (
                selected_plan.backup_id != verification.backup.id
                or not selected_plan.rebind_managed_storage
                or not selected_plan.restore_allowed
            ):
                raise LocalBackupValidationError(
                    "restore_managed_storage_rebind_rejected"
                )
        else:
            self.assert_restore_compatible(verification)
            selected_plan = None
        staged_database, staged_media = self._extract_staged_restore(
            verification,
            selected_plan,
        )
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

        sentinel_path = self._restore_sentinel_path()
        # Written *before* the first live-file mutation below, so a hard
        # kill at any point in this sequence -- not only a raised Python
        # exception, which `transaction.rollback()` already handles --
        # leaves durable evidence of exactly what was interrupted. See
        # `detect_interrupted_restore`.
        _atomic_write_text(
            sentinel_path,
            json.dumps(
                {
                    "token": token,
                    "backup_id": verification.backup.id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "rollback_database": str(rollback_database),
                    "rollback_media": str(rollback_media),
                }
            ),
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
            sentinel_path.unlink(missing_ok=True)
            return transaction
        except Exception as error:
            try:
                transaction.rollback()
            except Exception as rollback_error:
                # A genuinely unrecoverable state -- the sentinel is
                # deliberately *kept* here (not cleared) so Doctor/startup
                # can surface it rather than silently continue as if
                # nothing happened; the rollback paths it recorded are
                # exactly what a support conversation would need.
                raise LocalBackupRestoreError("restore_and_rollback_failed") from rollback_error
            sentinel_path.unlink(missing_ok=True)  # rollback succeeded -- back to the pre-restore state
            if isinstance(error, LocalBackupError):
                raise
            raise LocalBackupRestoreError("restore_file_replacement_failed") from error
