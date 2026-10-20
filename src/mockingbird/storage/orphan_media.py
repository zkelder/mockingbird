"""Reverse media integrity: managed files that no authoritative record owns.

The accepted Doctor media-integrity check goes database -> file ("this
MediaAsset row points at a missing file"). This module closes the other
direction, file -> database ("this file in managed storage belongs to nothing"),
under the contract in docs/orphan-media-integrity-recovery-contract.md.

Everything here is safe by construction:

* The scan is report-only. It never moves, deletes, or writes anything.
* Only the one configured `media_root` is ever walked, symlinks are never
  followed, and a symlink or special file is reported, never treated as an
  orphan candidate.
* An orphan finding requires a *complete* ownership set. If the database or
  the filesystem cannot be read completely the report says `incomplete` and
  carries no orphan claim -- "could not finish" is never presented as "clean".
* Ambiguity resolves toward "owned": a stored path that could refer to a file
  by either of the repository's two historical conventions claims it.
* Quarantine is an explicit, bounded, reversible move inside managed storage
  (`.orphan-quarantine/<batch>/`), with a sidecar manifest for audit/restore.
  Nothing is ever deleted and no database row is created, changed, or removed.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from typing import Iterator

from sqlalchemy import select
from sqlalchemy.engine import Connection, Engine

from mockingbird.storage.models import (
    MediaAssetModel,
    StorageCleanupItemModel,
    VisitModel,
    YardMapModel,
)

ORPHAN_QUARANTINE_DIRNAME = ".orphan-quarantine"
RETENTION_RECOVERY_DIRNAME = ".recovery"

# Top-level directories under the managed root that other, accepted subsystems
# own. They are excluded wholesale (never classified as orphan media):
# retention's `.recovery/<batch>/` is governed by StorageCleanupItem rows, this
# module's own quarantine by its manifests, and `audio_capture/` holds
# transient raw microphone segments the acoustic runtime deletes after copying.
EXCLUDED_TOP_LEVEL_DIRECTORIES: dict[str, str] = {
    RETENTION_RECOVERY_DIRNAME: "retention_recovery",
    ORPHAN_QUARANTINE_DIRNAME: "orphan_quarantine",
    "audio_capture": "working_capture",
}
TEMPORARY_SUFFIXES = (".tmp", ".part")
SYSTEM_FILENAMES = frozenset({".ds_store", "thumbs.db", "desktop.ini"})
WRITE_PROBE_PREFIX = ".mockingbird-write-check-"

# `_write_media_file` writes bytes before the owning row commits, so a file
# younger than this is "possibly mid-write", never an orphan and never movable.
DEFAULT_RECENT_WRITE_GRACE = timedelta(minutes=15)
# A temp artifact older than this is reported (informational) as stale; it is
# still never an orphan finding and never moved.
STALE_TEMPORARY_AGE = timedelta(hours=24)
MAX_REPORTED_FINDINGS = 200
MAX_QUARANTINE_PATHS = 200
DEFAULT_MAX_FILES = 2_000_000
_OWNER_FETCH_CHUNK = 5_000
_MANIFEST_NAME = "manifest.json"
_MANIFEST_SCHEMA = 1
_BATCH_ID_PATTERN = re.compile(r"^orphan-\d{8}T\d{6}Z-[0-9a-f]{8}$")

STATUS_CLEAN = "clean"
STATUS_ORPHANS_FOUND = "orphans_found"
STATUS_INCOMPLETE = "incomplete"


@dataclass(frozen=True)
class OrphanMediaFinding:
    relative_path: str
    size_bytes: int
    modified_at: datetime
    modified_ns: int
    # `unowned` is the only quarantine-eligible kind; the others are reported
    # for the operator but are never moved by this module.
    kind: str  # unowned | unsafe_entry


@dataclass
class OrphanMediaScanReport:
    scan_id: str
    started_at: datetime
    status: str
    media_root_present: bool
    files_examined: int = 0
    owned_files: int = 0
    owner_reference_count: int = 0
    distinct_owned_paths: int = 0
    references_outside_root: int = 0
    non_file_references: int = 0
    excluded_counts: dict[str, int] = field(default_factory=dict)
    excluded_directories: list[str] = field(default_factory=list)
    recently_written_count: int = 0
    stale_temporary_count: int = 0
    unsafe_entry_count: int = 0
    orphan_count: int = 0
    orphan_bytes: int = 0
    incomplete_reasons: list[str] = field(default_factory=list)
    findings: list[OrphanMediaFinding] = field(default_factory=list)
    findings_truncated: bool = False
    # Full eligible set for an in-process quarantine revalidation; never serialized.
    _eligible: dict[str, OrphanMediaFinding] = field(default_factory=dict, repr=False)

    @property
    def complete(self) -> bool:
        return not self.incomplete_reasons


@dataclass(frozen=True)
class QuarantineItemOutcome:
    relative_path: str
    outcome: str  # moved | skipped | failed
    code: str | None = None


@dataclass
class OrphanQuarantineResult:
    status: str  # completed | partial | failed | refused | nothing_to_move
    batch_id: str | None
    moved_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    moved_bytes: int = 0
    refusal_code: str | None = None
    items: list[QuarantineItemOutcome] = field(default_factory=list)


@dataclass
class OrphanRestoreResult:
    status: str  # completed | partial | failed | not_found
    batch_id: str
    restored_count: int = 0
    conflict_count: int = 0
    failed_count: int = 0
    items: list[QuarantineItemOutcome] = field(default_factory=list)


@dataclass(frozen=True)
class OrphanQuarantineBatchSummary:
    batch_id: str
    created_at: datetime
    item_count: int
    moved_count: int
    restored_count: int
    failed_count: int
    moved_bytes: int


# --------------------------------------------------------------------------
# Ownership
# --------------------------------------------------------------------------


def _owner_value_streams(connection: Connection) -> Iterator[str]:
    """Every database value that may name a managed media file.

    Streamed in chunks so memory is O(distinct short strings), never media
    bytes. A failure in any query propagates: a partial owner set must never
    be mistaken for a complete one.
    """

    queries = (
        select(MediaAssetModel.local_path),
        select(VisitModel.representative_media_path).where(VisitModel.representative_media_path.is_not(None)),
        select(YardMapModel.background_relative_path).where(YardMapModel.background_relative_path.is_not(None)),
        # A retention-staged file lives in `.recovery`, but its restore target
        # is still an owned location while the item is not terminal.
        select(StorageCleanupItemModel.original_local_path).where(
            StorageCleanupItemModel.state.not_in(("restored", "purged"))
        ),
    )
    for query in queries:
        result = connection.execution_options(stream_results=True).execute(query)
        try:
            while True:
                rows = result.fetchmany(_OWNER_FETCH_CHUNK)
                if not rows:
                    break
                for (value,) in rows:
                    if value is not None:
                        yield value
        finally:
            result.close()


def _root_forms(media_root: Path, relative_base: Path) -> tuple[str, ...]:
    configured = os.path.normpath(
        str(media_root) if media_root.is_absolute() else str(relative_base / media_root)
    )
    forms = [configured]
    try:
        resolved = os.path.normpath(str(media_root.resolve(strict=False)))
    except OSError:
        resolved = configured
    if resolved not in forms:
        forms.append(resolved)
    return tuple(forms)


def _owner_key(relative_posix: str) -> str:
    return os.path.normcase(relative_posix)


def _lexical_relative_key(candidate: str, root_forms: tuple[str, ...]) -> str | None:
    normalized = os.path.normpath(candidate)
    for root in root_forms:
        prefix = root.rstrip(os.sep) + os.sep
        if os.path.normcase(normalized).startswith(os.path.normcase(prefix)):
            relative = normalized[len(prefix):]
            if relative:
                return _owner_key(relative.replace(os.sep, "/"))
    return None


@dataclass
class _OwnerSet:
    keys: set[str]
    reference_count: int
    outside_root: int
    non_file: int


def _build_owner_set(
    engine: Engine, *, media_root: Path, relative_base: Path
) -> _OwnerSet:
    root_forms = _root_forms(media_root, relative_base)
    keys: set[str] = set()
    references = outside = non_file = 0
    with engine.connect() as connection:
        for raw in _owner_value_streams(connection):
            references += 1
            if not raw or "\x00" in raw or "://" in raw:
                # `demo://...` and similar are not filesystem references.
                non_file += 1
                continue
            if os.path.isabs(raw):
                candidates = [raw]
            else:
                # The repository stores `self.media_root / filename`, which is
                # cwd-relative when media_root is; older/other rows may be
                # media_root-relative. Either claim is honored (toward owned).
                candidates = [os.path.join(str(relative_base), raw), os.path.join(root_forms[0], raw)]
            claimed = False
            for candidate in candidates:
                key = _lexical_relative_key(candidate, root_forms)
                if key is not None:
                    keys.add(key)
                    claimed = True
            if not claimed:
                outside += 1
    return _OwnerSet(keys=keys, reference_count=references, outside_root=outside, non_file=non_file)


# --------------------------------------------------------------------------
# Scan
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class _WalkedFile:
    relative: str
    size: int
    mtime_ns: int


def _classify_artifact(name: str) -> str | None:
    lowered = name.lower()
    if name.startswith(WRITE_PROBE_PREFIX) or lowered.endswith(TEMPORARY_SUFFIXES):
        return "temporary"
    if lowered in SYSTEM_FILENAMES:
        return "system"
    return None


def scan_orphan_media(
    engine: Engine,
    media_root: Path | str,
    *,
    relative_base: Path | None = None,
    now: datetime | None = None,
    recent_write_grace: timedelta = DEFAULT_RECENT_WRITE_GRACE,
    max_files: int = DEFAULT_MAX_FILES,
    max_reported_findings: int = MAX_REPORTED_FINDINGS,
) -> OrphanMediaScanReport:
    """Report-only reverse scan. Never writes, moves, or deletes.

    Order matters: the filesystem is walked *first* and ownership is read
    second. A file written (and its row committed) during the walk is then
    either unseen or owned; the remaining window -- bytes on disk before the
    owning commit -- is closed by `recent_write_grace`.
    """

    media_root = Path(media_root)
    base = relative_base or Path.cwd()
    current = now or datetime.now(UTC)
    report = OrphanMediaScanReport(
        scan_id=f"orphan-scan-{uuid.uuid4().hex}",
        started_at=current,
        status=STATUS_CLEAN,
        media_root_present=False,
    )
    reasons: set[str] = set()
    excluded: Counter[str] = Counter()

    try:
        root_is_symlink = media_root.is_symlink()
        root_exists = media_root.exists()
    except OSError:
        report.status = STATUS_INCOMPLETE
        report.incomplete_reasons = ["media_root_unreadable"]
        return report
    if not root_exists:
        # Nothing has ever been written: genuinely nothing to own or orphan.
        return report
    report.media_root_present = True
    if root_is_symlink or not media_root.is_dir():
        report.status = STATUS_INCOMPLETE
        report.incomplete_reasons = ["media_root_unsafe"]
        return report

    walked: list[_WalkedFile] = []
    unsafe: list[OrphanMediaFinding] = []
    stack: list[tuple[str, str]] = [(str(media_root), "")]
    while stack:
        directory, relative_dir = stack.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = list(iterator)
        except OSError:
            reasons.add("directory_unreadable")
            continue
        for entry in entries:
            relative = f"{relative_dir}/{entry.name}" if relative_dir else entry.name
            try:
                if entry.is_symlink():
                    info = entry.stat(follow_symlinks=False)
                    unsafe.append(_finding(relative, info, "unsafe_entry"))
                    continue
                if entry.is_dir(follow_symlinks=False):
                    category = EXCLUDED_TOP_LEVEL_DIRECTORIES.get(entry.name) if not relative_dir else None
                    if category:
                        report.excluded_directories.append(category)
                        continue
                    stack.append((entry.path, relative))
                    continue
                info = entry.stat(follow_symlinks=False)
            except OSError:
                reasons.add("file_unreadable")
                continue
            if not stat.S_ISREG(info.st_mode):
                unsafe.append(_finding(relative, info, "unsafe_entry"))
                continue
            report.files_examined += 1
            if report.files_examined > max_files:
                reasons.add("file_limit_exceeded")
                stack.clear()
                break
            walked.append(_WalkedFile(relative=relative, size=info.st_size, mtime_ns=info.st_mtime_ns))

    try:
        owners = _build_owner_set(engine, media_root=media_root, relative_base=base)
    except Exception:  # noqa: BLE001 - any read failure means "cannot claim an orphan"
        reasons.add("database_unreadable")
        owners = None

    report.unsafe_entry_count = len(unsafe)
    if owners is not None:
        report.owner_reference_count = owners.reference_count
        report.distinct_owned_paths = len(owners.keys)
        report.references_outside_root = owners.outside_root
        report.non_file_references = owners.non_file

    if reasons:
        report.incomplete_reasons = sorted(reasons)
        report.status = STATUS_INCOMPLETE
        # Without a complete picture, report no orphan claim at all.
        report.excluded_counts = dict(sorted(excluded.items()))
        report.findings = sorted(unsafe, key=lambda item: item.relative_path)[:max_reported_findings]
        return report

    assert owners is not None
    eligible: dict[str, OrphanMediaFinding] = {}
    grace_cutoff_ns = int((current - recent_write_grace).timestamp() * 1_000_000_000)
    stale_cutoff_ns = int((current - STALE_TEMPORARY_AGE).timestamp() * 1_000_000_000)
    for item in walked:
        name = PurePosixPath(item.relative).name
        artifact = _classify_artifact(name)
        if artifact:
            excluded[artifact] += 1
            if artifact == "temporary" and item.mtime_ns < stale_cutoff_ns:
                report.stale_temporary_count += 1
            continue
        if _owner_key(item.relative) in owners.keys:
            report.owned_files += 1
            continue
        if item.mtime_ns > grace_cutoff_ns:
            report.recently_written_count += 1
            continue
        eligible[item.relative] = OrphanMediaFinding(
            relative_path=item.relative,
            size_bytes=item.size,
            modified_at=datetime.fromtimestamp(item.mtime_ns / 1_000_000_000, UTC),
            modified_ns=item.mtime_ns,
            kind="unowned",
        )

    report.excluded_counts = dict(sorted(excluded.items()))
    report.orphan_count = len(eligible)
    report.orphan_bytes = sum(item.size_bytes for item in eligible.values())
    ordered = sorted(eligible.values(), key=lambda item: item.relative_path)
    report._eligible = eligible
    report.findings = ordered[:max_reported_findings]
    report.findings_truncated = len(ordered) > max_reported_findings
    if report.unsafe_entry_count:
        remaining = max(0, max_reported_findings - len(report.findings))
        report.findings.extend(sorted(unsafe, key=lambda item: item.relative_path)[:remaining])
    report.status = STATUS_ORPHANS_FOUND if eligible else STATUS_CLEAN
    return report


def _finding(relative: str, info: os.stat_result, kind: str) -> OrphanMediaFinding:
    return OrphanMediaFinding(
        relative_path=relative,
        size_bytes=info.st_size,
        modified_at=datetime.fromtimestamp(info.st_mtime_ns / 1_000_000_000, UTC),
        modified_ns=info.st_mtime_ns,
        kind=kind,
    )


# --------------------------------------------------------------------------
# Quarantine / restore
# --------------------------------------------------------------------------


def normalize_requested_path(raw: str) -> str | None:
    """A managed-relative POSIX path, or None for anything unsafe."""

    if not isinstance(raw, str) or not raw or "\x00" in raw or "\\" in raw:
        return None
    path = PurePosixPath(raw)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", raw):
        return None
    parts = path.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        return None
    if parts[0] in EXCLUDED_TOP_LEVEL_DIRECTORIES:
        return None
    return "/".join(parts)


def _no_symlink_components(root: Path, relative: str) -> bool:
    current = root
    for part in PurePosixPath(relative).parts:
        current = current / part
        try:
            if current.is_symlink():
                return False
        except OSError:
            return False
    return True


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _move_without_overwrite(source: Path, destination: Path) -> None:
    """Atomic same-filesystem move that can never replace an existing file."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except FileExistsError:
        raise
    except OSError:
        # Hard links unsupported on this filesystem: fall back to an
        # exists-check plus atomic rename.
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(str(destination)) from None
        os.replace(source, destination)
        return
    try:
        os.unlink(source)
    except OSError:
        # Never leave two live copies while reporting success.
        os.unlink(destination)
        raise


def _write_manifest(batch_directory: Path, manifest: dict) -> None:
    target = batch_directory / _MANIFEST_NAME
    temporary = batch_directory / f".{_MANIFEST_NAME}.tmp"
    temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(temporary, target)


def _quarantine_root(media_root: Path) -> Path | None:
    root = media_root / ORPHAN_QUARANTINE_DIRNAME
    try:
        if root.is_symlink():
            return None
        root.mkdir(exist_ok=True)
        if root.is_symlink() or not root.resolve().is_relative_to(media_root.resolve()):
            return None
    except OSError:
        return None
    return root


def quarantine_orphans(
    engine: Engine,
    media_root: Path | str,
    relative_paths: list[str],
    *,
    relative_base: Path | None = None,
    now: datetime | None = None,
    recent_write_grace: timedelta = DEFAULT_RECENT_WRITE_GRACE,
) -> OrphanQuarantineResult:
    """Move explicitly selected, freshly revalidated orphans into recovery.

    Revalidation is performed here, not trusted from the caller: a fresh
    complete scan must still list each path as an orphan, ownership is reloaded
    a second time immediately before the moves, and each file's size/mtime must
    still match the scan. Anything else is skipped with a reason. An incomplete
    scan refuses the whole request. No database state is touched.
    """

    media_root = Path(media_root)
    base = relative_base or Path.cwd()
    if not relative_paths or len(relative_paths) > MAX_QUARANTINE_PATHS:
        return OrphanQuarantineResult(status="refused", batch_id=None, refusal_code="orphan_quarantine_selection_invalid")

    outcomes: list[QuarantineItemOutcome] = []
    requested: list[str] = []
    seen: set[str] = set()
    for raw in relative_paths:
        normalized = normalize_requested_path(raw)
        if normalized is None:
            outcomes.append(QuarantineItemOutcome(str(raw)[:200], "skipped", "unsafe_path"))
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        requested.append(normalized)

    report = scan_orphan_media(
        engine, media_root, relative_base=base, now=now, recent_write_grace=recent_write_grace
    )
    if not report.complete:
        return OrphanQuarantineResult(
            status="refused", batch_id=None, refusal_code="orphan_scan_incomplete", items=outcomes
        )

    candidates: list[OrphanMediaFinding] = []
    for relative in requested:
        finding = report._eligible.get(relative)
        if finding is None:
            outcomes.append(QuarantineItemOutcome(relative, "skipped", "not_unowned"))
        else:
            candidates.append(finding)
    skipped = sum(1 for item in outcomes if item.outcome == "skipped")
    if not candidates:
        return OrphanQuarantineResult(
            status="nothing_to_move", batch_id=None, skipped_count=skipped, items=outcomes
        )

    # Second, immediate ownership read: shrinks the scan -> move window to
    # (reload + per-file lstat). A failure here refuses before any move.
    try:
        fresh_owners = _build_owner_set(engine, media_root=media_root, relative_base=base)
    except Exception:  # noqa: BLE001
        return OrphanQuarantineResult(
            status="refused", batch_id=None, refusal_code="orphan_scan_incomplete", items=outcomes
        )

    quarantine_root = _quarantine_root(media_root)
    if quarantine_root is None:
        return OrphanQuarantineResult(
            status="refused", batch_id=None, refusal_code="orphan_quarantine_root_unsafe", items=outcomes
        )
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    for _attempt in range(5):
        batch_id = f"orphan-{stamp}-{uuid.uuid4().hex[:8]}"
        batch_directory = quarantine_root / batch_id
        try:
            batch_directory.mkdir(exist_ok=False)
            break
        except FileExistsError:
            continue
    else:
        return OrphanQuarantineResult(
            status="refused", batch_id=None, refusal_code="orphan_quarantine_root_unsafe", items=outcomes
        )
    created_at = (now or datetime.now(UTC)).isoformat()
    manifest: dict = {
        "schema": _MANIFEST_SCHEMA,
        "batch_id": batch_id,
        "created_at": created_at,
        "items": [
            {
                "relative_path": item.relative_path,
                "size_bytes": item.size_bytes,
                "modified_ns": item.modified_ns,
                "sha256": None,
                "state": "planned",
                "code": None,
            }
            for item in candidates
        ],
    }
    _write_manifest(batch_directory, manifest)

    moved = failed = 0
    moved_bytes = 0
    for entry, finding in zip(manifest["items"], candidates, strict=True):
        relative = finding.relative_path
        code: str | None = None
        try:
            source = media_root / relative
            if _owner_key(relative) in fresh_owners.keys:
                outcomes.append(QuarantineItemOutcome(relative, "skipped", "now_owned"))
                entry["state"], entry["code"] = "skipped", "now_owned"
                skipped += 1
                continue
            if not _no_symlink_components(media_root, relative):
                code = "symlink_path"
            else:
                try:
                    info = source.lstat()
                except FileNotFoundError:
                    outcomes.append(QuarantineItemOutcome(relative, "skipped", "already_missing"))
                    entry["state"], entry["code"] = "skipped", "already_missing"
                    skipped += 1
                    continue
                if not stat.S_ISREG(info.st_mode):
                    code = "not_a_regular_file"
                elif info.st_size != finding.size_bytes or info.st_mtime_ns != finding.modified_ns:
                    code = "changed_since_scan"
            if code is None:
                entry["sha256"] = _hash_file(source)
                _move_without_overwrite(source, batch_directory / relative)
                entry["state"] = "moved"
                moved += 1
                moved_bytes += finding.size_bytes
                outcomes.append(QuarantineItemOutcome(relative, "moved"))
                continue
        except FileExistsError:
            code = "destination_exists"
        except OSError:
            code = "move_failed"
        failed += 1
        entry["state"], entry["code"] = "failed", code
        outcomes.append(QuarantineItemOutcome(relative, "failed", code))
        _write_manifest(batch_directory, manifest)
    _write_manifest(batch_directory, manifest)

    if moved and not failed:
        status = "completed"
    elif moved:
        status = "partial"
    elif failed:
        status = "failed"
    else:
        status = "nothing_to_move"
    return OrphanQuarantineResult(
        status=status,
        batch_id=batch_id,
        moved_count=moved,
        skipped_count=skipped,
        failed_count=failed,
        moved_bytes=moved_bytes,
        items=outcomes,
    )


def _read_manifest(media_root: Path, batch_id: str) -> tuple[Path, dict] | None:
    if not _BATCH_ID_PATTERN.match(batch_id or ""):
        return None
    root = media_root / ORPHAN_QUARANTINE_DIRNAME
    try:
        if root.is_symlink() or not root.is_dir():
            return None
        directory = root / batch_id
        if directory.is_symlink() or not directory.is_dir():
            return None
        manifest = json.loads((directory / _MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(manifest, dict) or manifest.get("schema") != _MANIFEST_SCHEMA or not isinstance(manifest.get("items"), list):
        return None
    return directory, manifest


def restore_orphan_quarantine_batch(media_root: Path | str, batch_id: str) -> OrphanRestoreResult:
    """Return moved files to their original managed location.

    Never overwrites: a file that has since appeared at the original path is a
    reported conflict and the quarantined copy stays where it is. Items that
    never moved (interrupted batch) are left alone.
    """

    media_root = Path(media_root)
    loaded = _read_manifest(media_root, batch_id)
    if loaded is None:
        return OrphanRestoreResult(status="not_found", batch_id=batch_id)
    directory, manifest = loaded
    result = OrphanRestoreResult(status="completed", batch_id=batch_id)
    for entry in manifest["items"]:
        relative = normalize_requested_path(entry.get("relative_path", ""))
        if relative is None or entry.get("state") != "moved":
            continue
        stored = directory / relative
        original = media_root / relative
        parent = str(PurePosixPath(relative).parent)
        try:
            if not _no_symlink_components(directory, relative) or not stored.is_file() or stored.is_symlink():
                code = "quarantined_file_unavailable"
            elif parent != "." and not _no_symlink_components(media_root, parent):
                code = "symlink_path"
            else:
                try:
                    _move_without_overwrite(stored, original)
                except FileExistsError:
                    result.conflict_count += 1
                    result.items.append(QuarantineItemOutcome(relative, "skipped", "original_exists"))
                    continue
                entry["state"] = "restored"
                result.restored_count += 1
                result.items.append(QuarantineItemOutcome(relative, "moved"))
                continue
        except OSError:
            code = "restore_failed"
        result.failed_count += 1
        result.items.append(QuarantineItemOutcome(relative, "failed", code))
    _write_manifest(directory, manifest)
    if result.failed_count or result.conflict_count:
        result.status = "partial" if result.restored_count else "failed"
    return result


def list_orphan_quarantine_batches(media_root: Path | str, *, limit: int = 20) -> list[OrphanQuarantineBatchSummary]:
    media_root = Path(media_root)
    root = media_root / ORPHAN_QUARANTINE_DIRNAME
    try:
        if root.is_symlink() or not root.is_dir():
            return []
        names = sorted((p.name for p in root.iterdir() if _BATCH_ID_PATTERN.match(p.name)), reverse=True)
    except OSError:
        return []
    summaries: list[OrphanQuarantineBatchSummary] = []
    for name in names[:limit]:
        loaded = _read_manifest(media_root, name)
        if loaded is None:
            continue
        _, manifest = loaded
        items = manifest["items"]
        states = Counter(item.get("state") for item in items)
        try:
            created = datetime.fromisoformat(manifest.get("created_at", ""))
        except ValueError:
            continue
        summaries.append(
            OrphanQuarantineBatchSummary(
                batch_id=name,
                created_at=created,
                item_count=len(items),
                moved_count=states.get("moved", 0),
                restored_count=states.get("restored", 0),
                failed_count=states.get("failed", 0),
                moved_bytes=sum(int(item.get("size_bytes", 0)) for item in items if item.get("state") == "moved"),
            )
        )
    return summaries
