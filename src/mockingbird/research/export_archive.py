"""Bounded, deterministic ZIP of one already-generated research export, so the
browser can retrieve it without the user locating a Host directory.

This is deliberately not a general download manager: the caller passes only an
export *id* (never a path). The id is resolved strictly inside the managed
export root, symlinks are never followed or archived, and members are written
in sorted order with a fixed timestamp so the same export always yields the
same bytes. It reads only; it never creates or alters an export.
"""

from __future__ import annotations

import os
import re
import stat
import tempfile
import zipfile
from pathlib import Path

#: Generated ids look like `<name>-<UTC timestamp>-<8 hex>`; the name part is
#: caller-chosen, so only a plain token is accepted (no separators, no leading
#: dot -- temporary `.xxx.tmp` build directories are never downloadable).
_SAFE_EXPORT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,200}$")

#: Matches the export-time media bound (1 GiB) plus headroom for CSV/JSON.
EXPORT_ARCHIVE_MAX_BYTES = 1024 * 1024 * 1024 + 64 * 1024 * 1024
EXPORT_ARCHIVE_MAX_MEMBERS = 2100

_FIXED_ZIP_TIME = (1980, 1, 1, 0, 0, 0)


class ExportArchiveNotFound(Exception):
    """The id is malformed, unknown, stale, or not a plain managed directory."""


class ExportArchiveTooLarge(Exception):
    pass


def resolve_export_directory(export_root: Path, export_id: str) -> Path:
    if not _SAFE_EXPORT_ID.fullmatch(export_id):
        raise ExportArchiveNotFound(export_id)
    root = export_root.resolve(strict=False)
    candidate = root / export_id
    try:
        # lstat: a symlinked export directory is refused, not followed.
        mode = candidate.lstat().st_mode
    except OSError as error:
        raise ExportArchiveNotFound(export_id) from error
    if not stat.S_ISDIR(mode) or not candidate.resolve(strict=True).is_relative_to(root):
        raise ExportArchiveNotFound(export_id)
    return candidate


def _member_paths(directory: Path) -> list[tuple[str, Path]]:
    members: list[tuple[str, Path]] = []
    for current, dirnames, filenames in os.walk(directory, followlinks=False):
        dirnames.sort()
        for name in sorted(filenames):
            path = Path(current) / name
            # Regular files only: symlinks, devices, and fifos are skipped.
            if not stat.S_ISREG(path.lstat().st_mode):
                continue
            members.append((path.relative_to(directory).as_posix(), path))
    return sorted(members)


def build_export_archive(export_root: Path, export_id: str) -> tuple[Path, str]:
    """Returns (temporary zip path, download file name). The caller owns and
    must delete the temporary file."""

    directory = resolve_export_directory(export_root, export_id)
    members = _member_paths(directory)
    if not members:
        raise ExportArchiveNotFound(export_id)
    if len(members) > EXPORT_ARCHIVE_MAX_MEMBERS:
        raise ExportArchiveTooLarge(export_id)
    total = sum(path.lstat().st_size for _, path in members)
    if total > EXPORT_ARCHIVE_MAX_BYTES:
        raise ExportArchiveTooLarge(export_id)

    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
    handle, temp_name = tempfile.mkstemp(prefix="mockingbird-export-", suffix=".zip")
    os.close(handle)
    temp_path = Path(temp_name)
    try:
        with zipfile.ZipFile(temp_path, "w") as archive:
            for relative, path in members:
                info = zipfile.ZipInfo(f"{export_id}/{relative}", date_time=_FIXED_ZIP_TIME)
                info.external_attr = 0o644 << 16
                # Photos are already compressed; only text benefits.
                info.compress_type = (
                    zipfile.ZIP_STORED if relative.startswith("media/") else zipfile.ZIP_DEFLATED
                )
                try:
                    fd = os.open(path, flags)
                except OSError:
                    # Swapped for a symlink (or removed) after listing: skip.
                    continue
                with os.fdopen(fd, "rb") as reader, archive.open(info, "w") as writer:
                    while chunk := reader.read(1024 * 1024):
                        writer.write(chunk)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path, f"{export_id}.zip"
