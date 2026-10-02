"""Reverse media integrity (file -> database) and orphan quarantine.

Contract: docs/orphan-media-integrity-recovery-contract.md. These tests use a
real ProductRepository over an isolated tmp_path database/media root and never
touch persistent storage.
"""

from __future__ import annotations

import json
import os
import struct
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import func, select, text

from mockingbird.api.schemas import YardMapBlankCreate
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage import orphan_media
from mockingbird.storage.models import (
    MediaAssetModel,
    StreamModel,
    VisitModel,
)
from mockingbird.storage.orphan_media import (
    ORPHAN_QUARANTINE_DIRNAME,
    list_orphan_quarantine_batches,
    quarantine_orphans,
    restore_orphan_quarantine_batch,
    scan_orphan_media,
)

OLD = time.time() - 3 * 3600  # comfortably past the recent-write grace


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    return ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )


def _file(root: Path, relative: str, content: bytes = b"evidence", *, age: float | None = OLD) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    if age is not None:
        os.utime(path, (age, age))
    return path


def _own(repository: ProductRepository, stored_path: str, media_id: str | None = None) -> None:
    with repository.session_factory() as session:
        with session.begin():
            stream = session.scalar(select(StreamModel).order_by(StreamModel.id))
            assert stream is not None
            count = session.scalar(select(func.count()).select_from(MediaAssetModel)) or 0
            session.add(
                MediaAssetModel(
                    id=media_id or f"media-{count}",
                    source_id=stream.source_id,
                    stream_id=stream.id,
                    filename=Path(stored_path).name,
                    content_type="image/jpeg",
                    media_type="image",
                    local_path=stored_path,
                    original_filename=Path(stored_path).name,
                    file_size_bytes=1,
                    created_at=datetime.now(UTC),
                    notes=None,
                )
            )


def _scan(repository: ProductRepository, **kwargs):
    return scan_orphan_media(repository.engine, repository.media_root, **kwargs)


def _relatives(report) -> list[str]:
    return [item.relative_path for item in report.findings if item.kind == "unowned"]


# ---- ownership / classification -------------------------------------------


def test_missing_media_root_is_clean_not_incomplete(repository: ProductRepository) -> None:
    report = _scan(repository)
    assert report.status == "clean"
    assert report.complete and not report.media_root_present


# Header-only PNG: the Yard Map upload validates the declared dimensions, never decodes pixels.
_PNG_1X1 = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 64, 64) + b"\x08\x02\x00\x00\x00"


def test_owned_files_under_every_stored_path_convention_are_not_orphans(
    repository: ProductRepository, tmp_path: Path
) -> None:
    root = repository.media_root
    absolute = _file(root, "abs.jpg")
    _file(root, "rel-media-root.jpg")
    _file(root, "cwd-relative.jpg")
    _file(root, "dup.jpg")
    _file(root, "legacy-visit.jpg")
    _own(repository, str(absolute))  # absolute, as _write_media_file stores it
    _own(repository, "rel-media-root.jpg")  # media_root-relative
    _own(repository, "media/cwd-relative.jpg")  # relative_base-relative (media_root is tmp_path/media)
    _own(repository, str(root / "dup.jpg"))
    _own(repository, "dup.jpg")  # duplicate references to one file are legal
    with repository.session_factory() as session:
        with session.begin():
            visit = session.scalars(select(VisitModel)).first()
            assert visit is not None, "the seeded sample walkthrough provides a Visit"
            visit.representative_media_path = "legacy-visit.jpg"  # legacy owner with no MediaAsset row
    repository.create_blank_yard_map(YardMapBlankCreate(idempotency_key="blank"))
    state = repository.yard_map().map.state_token
    repository.replace_yard_map_background(
        content=_PNG_1X1, content_type="image/png", expected_state_token=state, idempotency_key="bg"
    )
    assert any((root / "property-map").iterdir())

    report = _scan(repository, relative_base=tmp_path)
    assert report.status == "clean", _relatives(report)
    assert report.orphan_count == 0
    assert report.owned_files == 6  # five files + the Yard Map background
    assert report.owner_reference_count >= 7 and report.distinct_owned_paths >= 6  # ambiguous relatives claim both readings


def test_unowned_file_is_reported_with_relative_path_and_no_mutation(repository: ProductRepository) -> None:
    root = repository.media_root
    orphan = _file(root, "stray/nested/lost.jpg", b"12345")
    before = (orphan.read_bytes(), orphan.stat().st_mtime_ns)
    report = _scan(repository)
    assert report.status == "orphans_found"
    assert _relatives(report) == ["stray/nested/lost.jpg"]
    assert report.orphan_bytes == 5 and report.orphan_count == 1
    assert str(root) not in json.dumps([f.relative_path for f in report.findings])
    assert (orphan.read_bytes(), orphan.stat().st_mtime_ns) == before
    assert not (root / ORPHAN_QUARANTINE_DIRNAME).exists()  # a scan never creates anything


def test_findings_are_deterministic_and_bounded(repository: ProductRepository) -> None:
    for index in (3, 1, 2):
        _file(repository.media_root, f"o{index}.jpg")
    first = _scan(repository, max_reported_findings=2)
    second = _scan(repository, max_reported_findings=2)
    assert _relatives(first) == _relatives(second) == ["o1.jpg", "o2.jpg"]
    assert first.orphan_count == 3 and first.findings_truncated


def test_recognized_artifacts_are_excluded_and_never_orphans(repository: ProductRepository) -> None:
    root = repository.media_root
    _file(root, ".recovery/batch-1/file.jpg")
    _file(root, f"{ORPHAN_QUARANTINE_DIRNAME}/orphan-x/file.jpg")
    _file(root, "audio_capture/stream-1/segment-00000001.wav")
    two_days = time.time() - 2 * 86400
    _file(root, "partial.tmp", age=two_days)
    _file(root, "upload.part", age=two_days)
    _file(root, ".mockingbird-write-check-123.tmp", age=two_days)
    _file(root, "Thumbs.db")
    report = _scan(repository)
    assert report.status == "clean"
    assert sorted(report.excluded_directories) == ["orphan_quarantine", "retention_recovery", "working_capture"]
    assert report.excluded_counts == {"system": 1, "temporary": 3}
    assert report.stale_temporary_count == 3  # old temp files are surfaced, still not orphans


def test_recently_written_file_is_possible_in_progress_write_not_orphan(repository: ProductRepository) -> None:
    root = repository.media_root
    _file(root, "mid-write.jpg", age=None)  # mtime = now
    report = _scan(repository)
    assert report.status == "clean"
    assert report.recently_written_count == 1
    # grace is time-based, so the same file becomes an orphan once it is old
    later = _scan(repository, now=datetime.now(UTC) + timedelta(hours=1))
    assert _relatives(later) == ["mid-write.jpg"]


# ---- unsafe paths -----------------------------------------------------------


def test_database_values_with_traversal_or_outside_paths_never_claim_inside_files(
    repository: ProductRepository, tmp_path: Path
) -> None:
    root = repository.media_root
    _file(root, "victim.jpg")
    outside = _file(tmp_path, "elsewhere/victim.jpg")
    _own(repository, "../media/../elsewhere/victim.jpg")  # lexically outside media_root
    _own(repository, str(outside))  # absolute, outside
    _own(repository, "demo://sample.jpg")  # not a filesystem reference
    report = _scan(repository, relative_base=tmp_path)
    assert _relatives(report) == ["victim.jpg"]
    assert report.references_outside_root == 2
    assert report.non_file_references >= 1  # also counts the seeded sample walkthrough's demo:// assets


def test_traversal_in_owner_value_that_resolves_inside_still_owns_the_file(
    repository: ProductRepository, tmp_path: Path
) -> None:
    _file(repository.media_root, "keep.jpg")
    _own(repository, str(repository.media_root / "sub" / ".." / "keep.jpg"))
    assert _scan(repository).status == "clean"


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_symlinks_are_reported_never_followed_and_never_orphan_candidates(
    repository: ProductRepository, tmp_path: Path
) -> None:
    root = repository.media_root
    root.mkdir(parents=True)
    secret_dir = tmp_path / "outside"
    _file(secret_dir, "secret.jpg")
    (root / "linked-dir").symlink_to(secret_dir, target_is_directory=True)
    (root / "linked-file.jpg").symlink_to(secret_dir / "secret.jpg")
    report = _scan(repository)
    assert report.status == "clean"  # symlinks are not orphans, and not a scan failure
    assert report.files_examined == 0
    assert report.unsafe_entry_count == 2
    assert {f.kind for f in report.findings} == {"unsafe_entry"}
    result = quarantine_orphans(repository.engine, root, ["linked-file.jpg", "linked-dir/secret.jpg"])
    assert result.status == "nothing_to_move"
    assert (secret_dir / "secret.jpg").exists()


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_symlinked_media_root_is_unsafe_and_incomplete(repository: ProductRepository, tmp_path: Path) -> None:
    real = tmp_path / "real-media"
    _file(real, "a.jpg")
    repository.media_root.symlink_to(real, target_is_directory=True)
    report = _scan(repository)
    assert report.status == "incomplete" and report.incomplete_reasons == ["media_root_unsafe"]
    assert report.orphan_count == 0


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="needs POSIX permissions and a non-root user")
def test_unreadable_directory_makes_scan_incomplete_not_clean(repository: ProductRepository) -> None:
    _file(repository.media_root, "ok.jpg")
    locked = repository.media_root / "locked"
    _file(repository.media_root, "locked/hidden.jpg")
    locked.chmod(0)
    try:
        report = _scan(repository)
    finally:
        locked.chmod(0o755)
    assert report.status == "incomplete"
    assert "directory_unreadable" in report.incomplete_reasons
    assert report.orphan_count == 0 and report.findings == []


def test_database_failure_is_incomplete_with_no_orphan_claim(repository: ProductRepository) -> None:
    _file(repository.media_root, "would-look-orphaned.jpg")
    with repository.engine.begin() as connection:
        connection.execute(text("ALTER TABLE media_assets RENAME TO media_assets_gone"))
    report = _scan(repository)
    assert report.status == "incomplete"
    assert report.incomplete_reasons == ["database_unreadable"]
    assert report.orphan_count == 0 and _relatives(report) == []


def test_file_limit_exceeded_is_incomplete(repository: ProductRepository) -> None:
    for index in range(4):
        _file(repository.media_root, f"f{index}.jpg")
    report = _scan(repository, max_files=2)
    assert report.status == "incomplete" and "file_limit_exceeded" in report.incomplete_reasons


# ---- quarantine -------------------------------------------------------------


def test_quarantine_moves_only_revalidated_orphans_and_writes_manifest(repository: ProductRepository) -> None:
    root = repository.media_root
    orphan = _file(root, "sub/lost.jpg", b"lost-bytes")
    owned = _file(root, "owned.jpg")
    _own(repository, str(owned))
    db_rows_before = _row_counts(repository)

    result = quarantine_orphans(repository.engine, root, ["sub/lost.jpg", "owned.jpg", "../escape.jpg", "nope.jpg"])

    assert result.status == "completed" and result.moved_count == 1 and result.failed_count == 0
    assert not orphan.exists() and owned.exists()
    moved = root / ORPHAN_QUARANTINE_DIRNAME / result.batch_id / "sub/lost.jpg"
    assert moved.read_bytes() == b"lost-bytes"
    manifest = json.loads((root / ORPHAN_QUARANTINE_DIRNAME / result.batch_id / "manifest.json").read_text())
    (item,) = [i for i in manifest["items"]]
    assert item["relative_path"] == "sub/lost.jpg" and item["state"] == "moved" and item["sha256"]
    assert str(root) not in json.dumps(manifest)  # portable: no absolute paths
    skipped = {i.relative_path: i.code for i in result.items if i.outcome == "skipped"}
    assert skipped["owned.jpg"] == "not_unowned" and skipped["nope.jpg"] == "not_unowned"
    assert skipped["../escape.jpg"] == "unsafe_path"
    assert _row_counts(repository) == db_rows_before  # database never mutated
    # the moved file is now excluded, so the library scans clean and recoverable
    assert _scan(repository).status == "clean"
    assert [b.batch_id for b in list_orphan_quarantine_batches(root)] == [result.batch_id]


def test_quarantine_refuses_everything_when_scan_is_incomplete(repository: ProductRepository) -> None:
    orphan = _file(repository.media_root, "lost.jpg")
    with repository.engine.begin() as connection:
        connection.execute(text("ALTER TABLE media_assets RENAME TO media_assets_gone"))
    result = quarantine_orphans(repository.engine, repository.media_root, ["lost.jpg"])
    assert result.status == "refused" and result.refusal_code == "orphan_scan_incomplete"
    assert orphan.exists()
    assert not (repository.media_root / ORPHAN_QUARANTINE_DIRNAME).exists()


def test_quarantine_rejects_recently_written_and_empty_or_oversized_selection(repository: ProductRepository) -> None:
    fresh = _file(repository.media_root, "fresh.jpg", age=None)
    result = quarantine_orphans(repository.engine, repository.media_root, ["fresh.jpg"])
    assert result.status == "nothing_to_move" and fresh.exists()
    assert quarantine_orphans(repository.engine, repository.media_root, []).status == "refused"
    too_many = [f"f{i}.jpg" for i in range(orphan_media.MAX_QUARANTINE_PATHS + 1)]
    assert quarantine_orphans(repository.engine, repository.media_root, too_many).status == "refused"


def test_race_ownership_appears_between_scan_and_move_is_never_moved(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    raced = _file(repository.media_root, "raced.jpg")
    real_build = orphan_media._build_owner_set
    calls = {"count": 0}

    def build_then_claim(engine, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:  # the immediate pre-move revalidation
            _own(repository, str(raced))
        return real_build(engine, **kwargs)

    monkeypatch.setattr(orphan_media, "_build_owner_set", build_then_claim)
    result = quarantine_orphans(repository.engine, repository.media_root, ["raced.jpg"])
    assert result.status == "nothing_to_move" and result.moved_count == 0
    assert [i.code for i in result.items] == ["now_owned"]
    assert raced.exists()


def test_race_file_changed_or_removed_between_scan_and_move(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    changed = _file(repository.media_root, "changed.jpg", b"a")
    gone = _file(repository.media_root, "gone.jpg", b"b")
    real_build = orphan_media._build_owner_set
    calls = {"count": 0}

    def mutate(engine, **kwargs):
        calls["count"] += 1
        if calls["count"] == 2:
            changed.write_bytes(b"different-length")
            gone.unlink()
        return real_build(engine, **kwargs)

    monkeypatch.setattr(orphan_media, "_build_owner_set", mutate)
    result = quarantine_orphans(repository.engine, repository.media_root, ["changed.jpg", "gone.jpg"])
    codes = {i.relative_path: (i.outcome, i.code) for i in result.items}
    assert codes["changed.jpg"] == ("failed", "changed_since_scan")
    assert codes["gone.jpg"] == ("skipped", "already_missing")
    assert result.status == "failed" and result.moved_count == 0 and result.failed_count == 1
    assert changed.exists()


def test_move_never_overwrites_an_existing_destination(tmp_path: Path) -> None:
    source = _file(tmp_path, "src/lost.jpg", b"new")
    destination = _file(tmp_path, "dest/lost.jpg", b"precious")
    with pytest.raises(FileExistsError):
        orphan_media._move_without_overwrite(source, destination)
    assert source.read_bytes() == b"new" and destination.read_bytes() == b"precious"


def test_batch_id_collision_retries_instead_of_reusing_a_directory(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository.media_root
    stamp = datetime(2026, 10, 2, 12, 0, 0, tzinfo=UTC)
    # Old relative to the injected clock, so it is past the recent-write grace.
    lost = _file(root, "lost.jpg", b"new", age=stamp.timestamp() - 3 * 3600)
    taken = _file(root, f"{ORPHAN_QUARANTINE_DIRNAME}/orphan-20261002T120000Z-{'ab' * 4}/lost.jpg", b"precious")
    # Scripted ids for the first draws (scan id, then the colliding batch id),
    # real random ids afterwards so unrelated callers of uuid4 are unaffected.
    scripted = ["ab" * 16, "ab" * 16]
    real_uuid4 = orphan_media.uuid.uuid4

    def uuid4():
        return type("U", (), {"hex": scripted.pop(0)})() if scripted else real_uuid4()

    monkeypatch.setattr(orphan_media, "uuid", type("M", (), {"uuid4": staticmethod(uuid4)}))
    result = quarantine_orphans(repository.engine, root, ["lost.jpg"], now=stamp)
    # scan_id consumed the first uuid; the batch id that follows must not reuse the taken directory
    assert result.status == "completed" and result.batch_id != f"orphan-20261002T120000Z-{'ab' * 4}"
    assert not scripted, "both scripted draws were consumed: the collision was actually exercised"
    assert taken.read_bytes() == b"precious" and not lost.exists()


def test_move_failure_midway_is_reported_and_never_claims_success(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = repository.media_root
    first = _file(root, "a.jpg", b"1")
    second = _file(root, "b.jpg", b"2")
    real_move = orphan_media._move_without_overwrite

    def flaky(source: Path, destination: Path) -> None:
        if source.name == "b.jpg":
            raise PermissionError("simulated interruption")
        real_move(source, destination)

    monkeypatch.setattr(orphan_media, "_move_without_overwrite", flaky)
    result = quarantine_orphans(repository.engine, root, ["a.jpg", "b.jpg"])
    assert result.status == "partial" and result.moved_count == 1 and result.failed_count == 1
    assert not first.exists() and second.exists()  # the failed file stays put
    manifest = json.loads((root / ORPHAN_QUARANTINE_DIRNAME / result.batch_id / "manifest.json").read_text())
    states = {i["relative_path"]: i["state"] for i in manifest["items"]}
    assert states == {"a.jpg": "moved", "b.jpg": "failed"}


def test_interrupted_batch_leaves_planned_items_and_restore_is_safe(repository: ProductRepository) -> None:
    root = repository.media_root
    stored = _file(root, "x.jpg", b"x")
    result = quarantine_orphans(repository.engine, root, ["x.jpg"])
    manifest_path = root / ORPHAN_QUARANTINE_DIRNAME / result.batch_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    # Simulate a crash after the manifest was planned but before the move.
    manifest["items"].append({"relative_path": "never.jpg", "size_bytes": 1, "modified_ns": 0, "sha256": None, "state": "planned", "code": None})
    manifest_path.write_text(json.dumps(manifest))
    restored = restore_orphan_quarantine_batch(root, result.batch_id)
    assert restored.status == "completed" and restored.restored_count == 1
    assert stored.read_bytes() == b"x"


def test_restore_round_trip_and_conflict_never_overwrites(repository: ProductRepository) -> None:
    root = repository.media_root
    _file(root, "d/one.jpg", b"one")
    _file(root, "two.jpg", b"two")
    result = quarantine_orphans(repository.engine, root, ["d/one.jpg", "two.jpg"])
    assert result.moved_count == 2
    (root / "two.jpg").write_bytes(b"replacement")  # something new took the original name
    restored = restore_orphan_quarantine_batch(root, result.batch_id)
    assert restored.restored_count == 1 and restored.conflict_count == 1 and restored.status == "partial"
    assert (root / "d/one.jpg").read_bytes() == b"one"
    assert (root / "two.jpg").read_bytes() == b"replacement"
    preserved = root / ORPHAN_QUARANTINE_DIRNAME / result.batch_id / "two.jpg"
    assert preserved.read_bytes() == b"two"  # the quarantined copy is retained
    assert restore_orphan_quarantine_batch(root, "orphan-../../etc").status == "not_found"
    assert restore_orphan_quarantine_batch(root, "orphan-20200101T000000Z-deadbeef").status == "not_found"


@pytest.mark.skipif(os.name == "nt", reason="symlink creation needs privileges on Windows")
def test_quarantine_root_symlink_is_refused(repository: ProductRepository, tmp_path: Path) -> None:
    root = repository.media_root
    _file(root, "lost.jpg")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (root / ORPHAN_QUARANTINE_DIRNAME).symlink_to(elsewhere, target_is_directory=True)
    result = quarantine_orphans(repository.engine, root, ["lost.jpg"])
    assert result.status == "refused" and result.refusal_code == "orphan_quarantine_root_unsafe"
    assert (root / "lost.jpg").exists() and not list(elsewhere.iterdir())


# ---- scale ------------------------------------------------------------------


def test_scale_scan_is_bounded_and_never_reads_media_bytes(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deterministic ~20k-file library: 2% orphans, 98% owned across a deep tree.

    Bounded = one walk + one streamed ownership read; byte-reading is a
    quarantine-only concern (audit hash), so any `open()` during a scan fails.
    """

    root = repository.media_root
    total, orphan_every = 20_000, 50
    expected_orphans: list[str] = []
    rows = []
    with repository.session_factory() as session:
        stream = session.scalar(select(StreamModel).order_by(StreamModel.id))
        assert stream is not None
        source_id, stream_id = stream.source_id, stream.id
    now = datetime.now(UTC)
    for index in range(total):
        relative = f"{index % 40:02d}/{index % 7}/img-{index:06d}.jpg" if index % 3 else f"img-{index:06d}.jpg"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        os.utime(path, (OLD, OLD))
        if index % orphan_every == 0:
            expected_orphans.append(relative)
            continue
        rows.append(
            MediaAssetModel(
                id=f"m{index}", source_id=source_id, stream_id=stream_id, filename=path.name,
                content_type="image/jpeg", media_type="image", local_path=str(path),
                original_filename=path.name, file_size_bytes=0, created_at=now, notes=None,
            )
        )
    with repository.session_factory() as session:
        with session.begin():
            session.add_all(rows)

    real_open = Path.open
    monkeypatch.setattr(Path, "open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("scan read media bytes")))
    monkeypatch.setattr("builtins.open", lambda *a, **k: (_ for _ in ()).throw(AssertionError("scan read media bytes")))
    started = time.monotonic()
    try:
        report = _scan(repository, max_reported_findings=10_000)
    finally:
        monkeypatch.undo()
        assert Path.open is real_open
    elapsed = time.monotonic() - started
    print(f"SCALE files={total} owned_rows={len(rows)} scan_seconds={elapsed:.2f}")

    assert report.status == "orphans_found"
    assert report.orphan_count == len(expected_orphans) == 400
    assert sorted(_relatives(report)) == sorted(expected_orphans)
    assert report.owned_files == total - 400
    assert elapsed < 30  # catches pathological (quadratic / per-row filesystem) behavior only


def _row_counts(repository: ProductRepository) -> dict[str, int]:
    with repository.engine.connect() as connection:
        return {
            table: connection.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
            for table in ("media_assets", "visits", "storage_cleanup_items")
        }
