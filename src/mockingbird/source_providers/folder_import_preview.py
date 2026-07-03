"""Dry-run folder import preview helper."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_ALLOWED_EXTENSIONS = [".jpg", ".jpeg", ".png", ".webp"]
DEFAULT_MAX_FILES = 500
MAX_MAX_FILES = 2_000
DEFAULT_MAX_DEPTH = 1
MAX_MAX_DEPTH = 8


@dataclass(frozen=True)
class FolderPreviewCandidate:
    relative_path: str
    file_name: str
    extension: str
    size_bytes: int | None
    modified_at: datetime | None
    planned_media_kind: str
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FolderPreviewSkipped:
    relative_path: str | None
    file_name: str | None
    reason: str
    message: str


@dataclass(frozen=True)
class FolderPreviewResult:
    recursive: bool
    allowed_extensions: list[str]
    candidates: list[FolderPreviewCandidate]
    skipped: list[FolderPreviewSkipped]
    total_known_bytes: int
    unknown_size_count: int
    scanned_at: datetime
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class _FolderEntry:
    path: Path
    depth: int
    skip_reason: str | None = None


class FolderImportPreviewError(ValueError):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def preview_folder_import(
    folder_path: str,
    *,
    recursive: bool = False,
    allowed_extensions: list[str] | None = None,
    max_files: int | None = DEFAULT_MAX_FILES,
    max_depth: int | None = DEFAULT_MAX_DEPTH,
) -> FolderPreviewResult:
    root = _validate_root(folder_path)
    normalized_allowed, extension_warnings = normalize_allowed_extensions(allowed_extensions)
    file_limit = _clamp_int(max_files, default=DEFAULT_MAX_FILES, minimum=1, maximum=MAX_MAX_FILES)
    depth_limit = _clamp_int(max_depth, default=DEFAULT_MAX_DEPTH, minimum=0, maximum=MAX_MAX_DEPTH)

    candidates: list[FolderPreviewCandidate] = []
    skipped: list[FolderPreviewSkipped] = []
    warnings = list(extension_warnings)
    truncated = False

    for entry in _walk_folder(root, recursive=recursive, max_depth=depth_limit):
        path = entry.path
        if len(candidates) >= file_limit:
            truncated = True
            break

        if entry.skip_reason == "max_depth_exceeded":
            skipped.append(
                _skipped(
                    path,
                    root,
                    "max_depth_exceeded",
                    "Directory is deeper than the configured preview depth.",
                )
            )
            continue

        if path.is_symlink():
            skipped.append(_skipped(path, root, "symlink", "Symlink paths are skipped."))
            continue

        if path.is_dir():
            if not recursive:
                skipped.append(
                    _skipped(
                        path,
                        root,
                        "directory_skipped",
                        "Directories are skipped unless recursive preview is enabled.",
                    )
                )
            continue

        if not _safe_is_file(path):
            skipped.append(_skipped(path, root, "not_file", "Only regular files are previewed."))
            continue

        try:
            resolved_path = path.resolve(strict=True)
        except OSError:
            skipped.append(_skipped(path, root, "unavailable", "Path metadata was unavailable."))
            continue
        if not _is_relative_to(resolved_path, root):
            skipped.append(
                _skipped(path, root, "outside_folder", "Resolved path is outside the folder.")
            )
            continue

        extension = path.suffix.lower()
        if extension not in SUPPORTED_EXTENSIONS:
            skipped.append(
                _skipped(
                    path,
                    root,
                    "unsupported_extension",
                    "Only JPEG, PNG, and WebP image extensions are supported for preview.",
                )
            )
            continue
        if extension not in normalized_allowed:
            skipped.append(
                _skipped(
                    path,
                    root,
                    "extension_not_allowed",
                    "This extension is not enabled for this preview request.",
                )
            )
            continue

        try:
            stat_result = path.stat()
            size_bytes = stat_result.st_size
            modified_at = datetime.fromtimestamp(stat_result.st_mtime, UTC)
        except OSError:
            size_bytes = None
            modified_at = None

        candidates.append(
            FolderPreviewCandidate(
                relative_path=_relative_path(path, root),
                file_name=path.name,
                extension=extension,
                size_bytes=size_bytes,
                modified_at=modified_at,
                planned_media_kind="image",
                warnings=[] if size_bytes is not None else ["File size could not be read."],
            )
        )

    if truncated:
        warnings.append(f"Preview truncated at {file_limit} candidate files.")

    return FolderPreviewResult(
        recursive=recursive,
        allowed_extensions=normalized_allowed,
        candidates=candidates,
        skipped=skipped,
        total_known_bytes=sum(candidate.size_bytes or 0 for candidate in candidates),
        unknown_size_count=sum(1 for candidate in candidates if candidate.size_bytes is None),
        scanned_at=datetime.now(UTC),
        warnings=warnings,
    )


def normalize_allowed_extensions(values: list[str] | None) -> tuple[list[str], list[str]]:
    if not values:
        return list(DEFAULT_ALLOWED_EXTENSIONS), []

    normalized: list[str] = []
    warnings: list[str] = []
    for value in values:
        for part in value.split(","):
            extension = part.strip().lower()
            if not extension:
                continue
            if not extension.startswith("."):
                extension = f".{extension}"
            if extension not in SUPPORTED_EXTENSIONS:
                warnings.append(f"Unsupported extension ignored: {extension}.")
                continue
            if extension not in normalized:
                normalized.append(extension)

    if not normalized:
        warnings.append("No supported extensions were requested; using the default image set.")
        return list(DEFAULT_ALLOWED_EXTENSIONS), warnings
    return normalized, warnings


def _validate_root(folder_path: str) -> Path:
    if not folder_path.strip():
        raise FolderImportPreviewError("folder_required")
    raw_root = Path(folder_path.strip()).expanduser()
    if raw_root.is_symlink():
        raise FolderImportPreviewError("folder_symlink")
    try:
        root = raw_root.resolve(strict=True)
    except FileNotFoundError as error:
        raise FolderImportPreviewError("folder_missing") from error
    except OSError as error:
        raise FolderImportPreviewError("folder_unavailable") from error
    if not root.is_dir():
        raise FolderImportPreviewError("folder_not_directory")
    return root


def _walk_folder(root: Path, *, recursive: bool, max_depth: int) -> list[_FolderEntry]:
    entries: list[_FolderEntry] = []
    stack: list[tuple[Path, int]] = [(root, 0)]
    while stack:
        current, depth = stack.pop()
        try:
            children = sorted(current.iterdir(), key=lambda item: item.name.lower())
        except OSError:
            continue
        for child in children:
            next_depth = depth + 1
            if not recursive or child.is_symlink() or not _safe_is_dir(child):
                entries.append(_FolderEntry(path=child, depth=next_depth))
                continue
            if next_depth > max_depth:
                entries.append(
                    _FolderEntry(
                        path=child,
                        depth=next_depth,
                        skip_reason="max_depth_exceeded",
                    )
                )
                continue
            entries.append(_FolderEntry(path=child, depth=next_depth))
            stack.append((child, next_depth))
    return entries


def _safe_is_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _safe_is_dir(path: Path) -> bool:
    try:
        return path.is_dir()
    except OSError:
        return False


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _skipped(path: Path, root: Path, reason: str, message: str) -> FolderPreviewSkipped:
    relative_path = _relative_path(path, root)
    return FolderPreviewSkipped(
        relative_path=relative_path,
        file_name=path.name,
        reason=reason,
        message=message,
    )


def _clamp_int(value: int | None, *, default: int, minimum: int, maximum: int) -> int:
    number = default if value is None else int(value)
    return min(max(number, minimum), maximum)
