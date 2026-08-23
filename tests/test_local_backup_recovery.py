from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
import zipfile
from tempfile import TemporaryDirectory

import httpx
import pytest

from mockingbird.api import main as api_main
from mockingbird.api.schemas import (
    SpeciesCandidatePackCreate,
    StreamSpeciesCandidatePackSelectionUpdate,
)
from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.backup import (
    BACKUP_ROOT_ENV_VAR,
    LocalBackupManager,
    LocalBackupUnsupportedError,
    LocalBackupValidationError,
)
from mockingbird.storage.database import (
    CURRENT_DATABASE_SCHEMA_VERSION,
    create_database_engine,
)
from mockingbird.storage.models import (
    BioClipIdentificationAttemptModel,
    MediaAssetModel,
    MonitoringExposureIntervalModel,
    StreamRuntimeCheckpointModel,
)
from tests.conftest import LegacyAuthenticatedSyncTestClient


client = LegacyAuthenticatedSyncTestClient(app)


def _repository(tmp_path: Path) -> ProductRepository:
    return ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
        classifier_manifest_export_root=tmp_path / "classifier-exports",
    )


def _manager(repository: ProductRepository, tmp_path: Path) -> LocalBackupManager:
    return LocalBackupManager(
        db_url=repository.db_url,
        media_root=repository.media_root,
        backup_root=tmp_path / "backups",
    )


def test_backup_captures_wal_database_and_managed_media(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.media_root.mkdir(parents=True)
    media_path = repository.media_root / "nested" / "visit.jpg"
    media_path.parent.mkdir()
    media_path.write_bytes(b"original bird frame")
    manager = _manager(repository, tmp_path)

    verification = manager.create_backup()

    assert verification.backup.verification_status == "verified"
    assert verification.backup.restore_compatible is True
    assert verification.backup.media_file_count == 1
    assert verification.backup.media_size_bytes == len(b"original bird frame")
    assert verification.backup.archive_path.suffix == ".mbbackup"
    assert len(repository.list_review_labels()) == 1

    with zipfile.ZipFile(verification.backup.archive_path) as archive:
        assert set(archive.namelist()) == {
            "manifest.json",
            "database.sqlite3",
            "media/nested/visit.jpg",
        }

    repository.close()


def test_verified_schema_one_backup_restores_through_known_migration(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    repository.close()

    engine = create_database_engine(repository.db_url)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE bioclip_identification_attempts")
        connection.exec_driver_sql("DROP TABLE stream_runtime_checkpoints")
        connection.exec_driver_sql("DROP TABLE stream_monitoring_policies")
        connection.exec_driver_sql(
            "UPDATE mockingbird_schema SET version = 1 WHERE singleton_id = 1"
        )
    engine.dispose()

    manager = _manager(repository, tmp_path)
    backup = manager.create_backup()
    assert backup.backup.database_schema_version == 1
    assert backup.backup.restore_compatible is True

    transaction = manager.replace_live_files(manager.verify_backup(backup.backup.id))
    migrated_repository = _repository(tmp_path)
    try:
        policy = migrated_repository.get_stream_monitoring_policy(
            "stream-backyard-feeder"
        )
        assert (
            migrated_repository.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        )
        assert policy is not None
        assert policy.mode == "off"
        transaction.commit()
    finally:
        migrated_repository.close()


def test_backup_restore_preserves_bioclip_attempt_evidence(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.media_root.mkdir(parents=True)
    media_path = repository.media_root / "bioclip-backup.jpg"
    media_path.write_bytes(b"bounded BioCLIP input")
    now = datetime.now(UTC)
    with repository.engine.begin() as connection:
        connection.execute(
            MediaAssetModel.__table__.insert().values(
                id="media-bioclip-backup",
                source_id="source-backyard-demo",
                stream_id="stream-backyard-feeder",
                filename="bioclip-backup.jpg",
                content_type="image/jpeg",
                media_type="image",
                local_path=str(media_path),
                original_filename="bioclip-backup.jpg",
                file_size_bytes=media_path.stat().st_size,
                created_at=now,
                notes="Storage preservation fixture.",
            )
        )
        connection.execute(
            BioClipIdentificationAttemptModel.__table__.insert().values(
                id="bioclip-attempt-backup",
                target_type="visit",
                target_id="visit-bird-feeder-001",
                event_id="event-bird-feeder-001",
                visit_id="visit-bird-feeder-001",
                media_asset_id="media-bioclip-backup",
                source_id="source-backyard-demo",
                stream_id="stream-backyard-feeder",
                zone_id="zone-feeder",
                motion_evidence_id=None,
                detection_proposal_id=None,
                resulting_species_suggestion_id=None,
                adapter_id="bioclip-2",
                started_at=now,
                completed_at=now,
                duration_ms=47,
                timeout_limit_ms=30_000,
                timeout_exceeded=False,
                outcome="failed",
                crop_source="activity",
                crop_provenance_json=(
                    '{"box_normalized":{"height":0.5,"width":0.5,"x":0.1,"y":0.1}}'
                ),
                model_provenance_json=None,
                preprocessing_json=None,
                candidate_manifest_json=None,
                candidate_set_count=None,
                candidate_set_sha256=None,
                candidate_set_version=None,
                candidate_manifest_complete=False,
                error_code="runtime_unavailable",
                error_stage="model_load",
                error_detail="The optional local model runtime was unavailable.",
                provenance_schema_version=1,
            )
        )

    manager = _manager(repository, tmp_path)
    backup = manager.create_backup()
    with repository.engine.begin() as connection:
        connection.execute(
            BioClipIdentificationAttemptModel.__table__.delete().where(
                BioClipIdentificationAttemptModel.id == "bioclip-attempt-backup"
            )
        )
    repository.close()

    transaction = manager.replace_live_files(manager.verify_backup(backup.backup.id))
    restored_repository = _repository(tmp_path)
    try:
        with restored_repository.engine.connect() as connection:
            restored = (
                connection.execute(
                    BioClipIdentificationAttemptModel.__table__.select().where(
                        BioClipIdentificationAttemptModel.id == "bioclip-attempt-backup"
                    )
                )
                .mappings()
                .one()
            )
        assert restored["outcome"] == "failed"
        assert restored["duration_ms"] == 47
        assert restored["error_code"] == "runtime_unavailable"
        transaction.commit()
    finally:
        restored_repository.close()


def test_restore_replaces_database_and_media_as_one_recoverable_pair(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    repository.media_root.mkdir(parents=True)
    media_path = repository.media_root / "visit.jpg"
    media_path.write_bytes(b"backup version")
    manager = _manager(repository, tmp_path)
    backup = manager.create_backup()

    with repository.engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM review_labels")
    media_path.write_bytes(b"changed version")
    (repository.media_root / "new-after-backup.jpg").write_bytes(b"new")
    assert len(repository.list_review_labels()) == 0
    repository.close()

    selected = manager.verify_backup(backup.backup.id)
    transaction = manager.replace_live_files(selected)
    restored_repository = _repository(tmp_path)
    try:
        assert len(restored_repository.list_review_labels()) == 1
        assert media_path.read_bytes() == b"backup version"
        assert not (restored_repository.media_root / "new-after-backup.jpg").exists()
        transaction.commit()
    finally:
        restored_repository.close()


def test_restore_transaction_rolls_database_and_media_back(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.media_root.mkdir(parents=True)
    media_path = repository.media_root / "visit.jpg"
    media_path.write_bytes(b"backup version")
    manager = _manager(repository, tmp_path)
    backup = manager.create_backup()

    with repository.engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM review_labels")
    media_path.write_bytes(b"current version")
    repository.close()

    transaction = manager.replace_live_files(manager.verify_backup(backup.backup.id))
    transaction.rollback()

    recovered_repository = _repository(tmp_path)
    try:
        assert len(recovered_repository.list_review_labels()) == 0
        assert media_path.read_bytes() == b"current version"
    finally:
        recovered_repository.close()


def test_verification_rejects_duplicate_or_traversal_members(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    manager = _manager(repository, tmp_path)
    backup = manager.create_backup()
    repository.close()

    with zipfile.ZipFile(backup.backup.archive_path, mode="a") as archive:
        archive.writestr("../escape.txt", b"unsafe")

    with pytest.raises(LocalBackupValidationError):
        manager.verify_backup(backup.backup.id)
    assert not (tmp_path / "escape.txt").exists()


def test_library_rejects_archive_whose_filename_does_not_match_its_identity(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    manager = _manager(repository, tmp_path)
    backup = manager.create_backup()
    repository.close()

    mismatched_id = "0" * 32
    mismatched_path = backup.backup.archive_path.with_name(f"{mismatched_id}.mbbackup")
    backup.backup.archive_path.replace(mismatched_path)

    library = manager.list_backups()
    assert library.backups == []
    assert library.unreadable_backup_count == 1
    with pytest.raises(LocalBackupValidationError):
        manager.verify_backup(mismatched_id)


def test_backup_rejects_symbolic_links_in_managed_media(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.media_root.mkdir(parents=True)
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"outside")
    link = repository.media_root / "linked.jpg"
    try:
        link.symlink_to(outside)
    except OSError:
        repository.close()
        pytest.skip("Symbolic links are unavailable for this Windows test account.")

    with pytest.raises(LocalBackupUnsupportedError):
        _manager(repository, tmp_path).create_backup()
    repository.close()


@pytest.fixture
def api_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(BACKUP_ROOT_ENV_VAR, str(tmp_path / "backups"))
    repository = _repository(tmp_path)
    repository.media_root.mkdir(parents=True)
    (repository.media_root / "api-visit.jpg").write_bytes(b"api backup version")
    configure_repository(repository)
    yield repository
    configure_repository(None)


def test_backup_api_create_list_verify_download_and_import(
    api_repository: ProductRepository,
) -> None:
    created_response = client.post("/api/settings/backups")
    assert created_response.status_code == 201
    created = created_response.json()
    assert created["verified"] is True
    assert created["backup"]["verification_status"] == "verified"
    backup_id = created["backup"]["id"]

    list_response = client.get("/api/settings/backups")
    assert list_response.status_code == 200
    assert list_response.json()["backups"][0]["id"] == backup_id
    # Appliance / Storage / Privacy / Recovery v1: `create_backup` already
    # ran a real, full verification internally -- `list_backups` now
    # honestly reflects that (via the durable marker `verify_archive`
    # writes) instead of always claiming "not_checked" regardless of
    # history. See test_list_backups_reports_not_checked_for_a_backup_that_
    # was_never_verified for the genuinely-unverified case.
    assert list_response.json()["backups"][0]["verification_status"] == "verified"

    verify_response = client.post(f"/api/settings/backups/{backup_id}/verify")
    assert verify_response.status_code == 200
    assert verify_response.json()["backup"]["verification_status"] == "verified"

    download_response = client.get(f"/api/settings/backups/{backup_id}/download")
    assert download_response.status_code == 200
    assert download_response.content.startswith(b"PK")
    assert ".mbbackup" in download_response.headers["content-disposition"]

    import_response = client.post(
        "/api/settings/backups/import",
        files={
            "file": ("saved.mbbackup", download_response.content, "application/zip")
        },
    )
    assert import_response.status_code == 201
    assert import_response.json()["backup"]["id"] == backup_id


def test_list_backups_reports_not_checked_for_a_backup_that_was_never_verified(
    tmp_path: Path,
) -> None:
    """The honest counterpart to the fix above: a `.mbbackup` file placed
    directly into the backup directory (never through `create_backup`/
    `import_backup`/`verify_backup`) has no verified marker at all, so
    `list_backups` correctly still reports `not_checked` for it -- the fix
    is that "verified" now means something real, not that everything
    reports "verified" unconditionally."""

    repository = _repository(tmp_path)
    repository.media_root.mkdir(parents=True)
    manager = _manager(repository, tmp_path)
    verification = manager.create_backup()
    manager._verified_marker_path(verification.backup.id).unlink()  # simulate a marker that never existed

    library = manager.list_backups()

    assert library.backups[0].id == verification.backup.id
    assert library.backups[0].verification_status == "not_checked"
    repository.close()


def test_cleanup_orphaned_temporary_artifacts_removes_only_old_temp_files(
    tmp_path: Path,
) -> None:
    """Simulates the one thing this cleanup exists for: a hard process kill
    mid-backup leaves a `.creating-*`/`.snapshot-*` file behind forever.
    Age-gated so a genuinely in-progress operation is never touched, and a
    real, correctly-named backup is never mistaken for an orphan."""

    repository = _repository(tmp_path)
    repository.media_root.mkdir(parents=True)
    manager = _manager(repository, tmp_path)
    real_backup = manager.create_backup()

    old_orphan = manager.backup_root / ".creating-deadbeefdeadbeefdeadbeefdeadbeef.mbbackup"
    old_orphan.write_bytes(b"incomplete")
    old_snapshot = manager.backup_root / ".snapshot-deadbeefdeadbeefdeadbeefdeadbeef.sqlite3"
    old_snapshot.write_bytes(b"incomplete")
    recent_orphan = manager.backup_root / ".import-cafefeedcafefeedcafefeedcafefeed.mbbackup"
    recent_orphan.write_bytes(b"still-in-progress")
    import os as _os

    old_timestamp = datetime.now(UTC).timestamp() - 7200
    _os.utime(old_orphan, (old_timestamp, old_timestamp))
    _os.utime(old_snapshot, (old_timestamp, old_timestamp))
    # recent_orphan keeps its just-created (fresh) mtime.

    removed = manager.cleanup_orphaned_temporary_artifacts(min_age_seconds=3600)

    assert removed == 2
    assert not old_orphan.exists()
    assert not old_snapshot.exists()
    assert recent_orphan.exists()  # too young to touch -- could be a real in-progress operation
    assert real_backup.backup.archive_path.exists()  # never mistaken for an orphan
    repository.close()


def test_detect_interrupted_restore_is_none_on_a_normal_installation(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    manager = _manager(repository, tmp_path)
    assert manager.detect_interrupted_restore() is None
    repository.close()


def test_replace_live_files_clears_the_sentinel_after_recovering_from_a_hard_kill(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A hard process kill mid-swap is simulated by making the *forward*
    `os.replace` call that promotes the staged database fail, while
    everything else (including `RestoreFileTransaction.rollback()`'s own
    `os.replace` calls) proceeds normally -- the common, recoverable case.
    Proves the sentinel `replace_live_files` writes before its first mutation
    is cleared once rollback genuinely restores the pre-restore state."""

    from mockingbird.storage import backup as backup_module

    repository = _repository(tmp_path)
    repository.media_root.mkdir(parents=True)
    (repository.media_root / "visit.jpg").write_bytes(b"backup version")
    manager = _manager(repository, tmp_path)
    verification = manager.create_backup()
    (repository.media_root / "visit.jpg").write_bytes(b"current version")
    repository.close()

    real_replace = backup_module.os.replace
    database_path = manager.database_path
    promote_attempts = {"count": 0}

    def selective_replace(src, dst):
        # Fires exactly on "promote staged database to the live path" --
        # the first time `dst` is the live database path -- but lets
        # `RestoreFileTransaction.rollback()`'s own later attempt to
        # restore the *original* database back to that same live path
        # succeed normally (the recoverable case this test proves).
        if Path(dst) == database_path:
            promote_attempts["count"] += 1
            if promote_attempts["count"] == 1:
                raise OSError("simulated hard kill mid-restore")
        return real_replace(src, dst)

    monkeypatch.setattr(backup_module.os, "replace", selective_replace)

    with pytest.raises(backup_module.LocalBackupRestoreError):
        manager.replace_live_files(manager.verify_backup(verification.backup.id))

    monkeypatch.undo()  # detect_interrupted_restore/re-reading media below must use the real os.replace
    assert manager.detect_interrupted_restore() is None  # rollback succeeded -- no longer "in progress"
    assert (repository.media_root / "visit.jpg").read_bytes() == b"current version"


def test_replace_live_files_keeps_the_sentinel_when_rollback_itself_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The genuinely unrecoverable case: the forward swap fails *and* the
    resulting rollback attempt also fails. The sentinel must survive so a
    later Doctor run / product startup can surface it -- silently
    continuing as if nothing happened would be the unsafe outcome here."""

    from mockingbird.storage import backup as backup_module

    repository = _repository(tmp_path)
    repository.media_root.mkdir(parents=True)
    (repository.media_root / "visit.jpg").write_bytes(b"backup version")
    manager = _manager(repository, tmp_path)
    verification = manager.create_backup()
    repository.close()

    real_replace = backup_module.os.replace
    database_path = manager.database_path

    def always_fail_promote(src, dst):
        # Fails *every* attempt to write to the live database path --
        # both the forward promote and rollback's own later attempt to
        # restore the original database -- the unrecoverable case.
        if Path(dst) == database_path:
            raise OSError("simulated unrecoverable hard kill")
        return real_replace(src, dst)

    monkeypatch.setattr(backup_module.os, "replace", always_fail_promote)

    with pytest.raises(backup_module.LocalBackupRestoreError, match="restore_and_rollback_failed"):
        manager.replace_live_files(manager.verify_backup(verification.backup.id))

    monkeypatch.undo()
    interrupted = manager.detect_interrupted_restore()
    assert interrupted is not None
    assert interrupted["backup_id"] == verification.backup.id

    # Doctor must surface this plainly, not fold it into ordinary staleness.
    from mockingbird.diagnostics import doctor

    gathered = doctor._gather_backup(
        db_url=repository.db_url, media_root=repository.media_root, backup_root=manager.backup_root
    )
    result = doctor._interpret_backup(gathered, now=datetime.now(UTC))
    assert result.status == doctor.DoctorStatus.WARN
    assert "did not finish" in result.summary


def test_backup_api_restore_requires_confirmation(
    api_repository: ProductRepository,
) -> None:
    backup_id = client.post("/api/settings/backups").json()["backup"]["id"]

    response = client.post(
        f"/api/settings/backups/{backup_id}/restore",
        json={"confirm": False},
    )

    assert response.status_code == 400
    assert "Confirm restore" in response.json()["detail"]


def test_backup_api_restore_keeps_pre_restore_safety_backup(
    api_repository: ProductRepository,
) -> None:
    backup_id = client.post("/api/settings/backups").json()["backup"]["id"]
    with api_repository.engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM review_labels")
    (api_repository.media_root / "api-visit.jpg").write_bytes(b"changed after backup")
    assert client.get("/api/settings/local-data").json()["review_label_count"] == 0

    response = client.post(
        f"/api/settings/backups/{backup_id}/restore",
        json={"confirm": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"]["review_label_count"] == 1
    assert body["safety_backup"]["kind"] == "pre_restore"
    assert (
        api_repository.media_root / "api-visit.jpg"
    ).read_bytes() == b"api backup version"
    backups = client.get("/api/settings/backups").json()["backups"]
    assert {item["kind"] for item in backups} == {"manual", "pre_restore"}


def test_backup_api_restore_holds_an_armed_stream(api_repository: ProductRepository) -> None:
    """End-to-end proof that the real `POST .../restore` route (not only the
    underlying repository methods in isolation) applies the restore hold:
    arm a Stream, back it up while armed, restore over the API, and confirm
    `GET .../runtime-status` -- the same route Stream Detail reads -- now
    reports `safety_hold_active=True` and a `restore_hold` reason."""

    stream_id = "stream-backyard-feeder"
    api_repository.set_stream_monitoring_enabled(
        stream_id, enabled=True, idempotency_key="arm-before-api-backup",
    )
    backup_id = client.post("/api/settings/backups").json()["backup"]["id"]

    response = client.post(
        f"/api/settings/backups/{backup_id}/restore", json={"confirm": True},
    )
    assert response.status_code == 200

    status = client.get(f"/api/streams/{stream_id}/runtime-status").json()
    assert status["safety_hold_active"] is True
    assert status["last_stop_reason"] == "restore_hold"

    health = client.get("/api/product/health").json()
    assert health["ready"] is True, "a deliberate, safe restore hold must not alarm the aggregate Dashboard"


def test_failed_repository_reopen_rolls_back_before_returning_error(
    api_repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backup_id = client.post("/api/settings/backups").json()["backup"]["id"]
    with api_repository.engine.begin() as connection:
        connection.exec_driver_sql("DELETE FROM review_labels")
    (api_repository.media_root / "api-visit.jpg").write_bytes(
        b"current before failed restore"
    )

    original_open = api_main._open_product_repository
    calls = 0

    def fail_first_open(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated restored repository startup failure")
        return original_open(**kwargs)

    monkeypatch.setattr(api_main, "_open_product_repository", fail_first_open)
    response = client.post(
        f"/api/settings/backups/{backup_id}/restore",
        json={"confirm": True},
    )

    assert response.status_code == 500
    assert client.get("/api/settings/local-data").json()["review_label_count"] == 0
    assert (api_repository.media_root / "api-visit.jpg").read_bytes() == (
        b"current before failed restore"
    )


def test_backup_restore_preserves_stream_candidate_pack_selection(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    pack = repository.create_species_candidate_pack(
        SpeciesCandidatePackCreate(
            display_name="Backup feeder pack",
            taxonomy_label_ids=["tufted_titmouse", "carolina_chickadee"],
        )
    )
    repository.set_stream_species_candidate_pack_selection(
        "stream-backyard-feeder",
        StreamSpeciesCandidatePackSelectionUpdate(candidate_pack_id=pack.id),
    )
    manager = _manager(repository, tmp_path)
    backup = manager.create_backup()
    repository.close()

    transaction = manager.replace_live_files(manager.verify_backup(backup.backup.id))
    restored_repository = _repository(tmp_path)
    try:
        selection = restored_repository.get_stream_species_candidate_pack_selection(
            "stream-backyard-feeder"
        )
        assert selection is not None
        assert selection.selected_pack_id == pack.id
        assert selection.effective_pack.content_sha256 == pack.content_sha256
        transaction.commit()
    finally:
        restored_repository.close()


def test_backup_restore_closes_open_exposure_as_historical_evidence() -> None:
    with TemporaryDirectory(dir="/tmp") as temporary_directory:
        root = Path(temporary_directory)
        repository = _repository(root)
        now = datetime(2026, 7, 20, 9, tzinfo=UTC)
        with repository.session_factory() as session:
            with session.begin():
                session.add(
                    MonitoringExposureIntervalModel(
                        id="exposure-backup-open",
                        stream_id="stream-backyard-feeder",
                        source_id="source-backyard-demo",
                        runtime_generation_id="backup-generation",
                        started_at=now,
                        last_confirmed_fresh_at=now + timedelta(minutes=5),
                        ended_at=None,
                        close_reason=None,
                        created_at=now,
                        updated_at=now + timedelta(minutes=5),
                    )
                )
        manager = _manager(repository, root)
        backup = manager.create_backup()
        plan = manager.create_restore_plan(manager.verify_backup(backup.backup.id))
        assert plan.expected_entity_counts["monitoring_exposure_intervals"] == 1
        repository.close()

        transaction = manager.replace_live_files(manager.verify_backup(backup.backup.id))
        restored_repository = _repository(root)
        restored_repository.prepare_for_supervision("local-backup-restore")
        try:
            with restored_repository.session_factory() as session:
                restored = session.get(
                    MonitoringExposureIntervalModel, "exposure-backup-open"
                )
                assert restored is not None
                assert restored.stream_id == "stream-backyard-feeder"
                assert restored.source_id == "source-backyard-demo"
                assert restored.ended_at is not None
                assert restored.ended_at.replace(tzinfo=UTC) == now + timedelta(minutes=5)
                assert restored.close_reason == "unclean_restart"
            status = restored_repository.get_stream_runtime_status(
                "stream-backyard-feeder", now=now + timedelta(minutes=6)
            )
            assert status is not None
            assert status.exposure_interval_active is False
            transaction.commit()
        finally:
            restored_repository.close()


def test_restore_holds_an_armed_stream_rather_than_letting_it_silently_resume() -> None:
    """docs/local-backup-recovery-design.md and docs/durable-camera-monitor-
    lifecycle-design.md both document a persisted `restore_hold`: an armed
    Stream's *policy* survives restore unchanged (it is the restored durable
    truth), but the *runtime* must not resume monitoring until the user
    explicitly resumes it -- including after the next application restart,
    not merely within the current process. Prove the hold is actually
    applied and persisted, not merely documented."""

    with TemporaryDirectory(dir="/tmp") as temporary_directory:
        root = Path(temporary_directory)
        repository = _repository(root)
        repository.set_stream_monitoring_enabled(
            "stream-backyard-feeder", enabled=True, idempotency_key="arm-before-backup",
        )
        manager = _manager(repository, root)
        backup = manager.create_backup()
        repository.close()

        transaction = manager.replace_live_files(manager.verify_backup(backup.backup.id))
        restored_repository = _repository(root)
        restored_repository.prepare_for_supervision("local-backup-restore")
        restored_repository.apply_restore_hold()
        try:
            policy = restored_repository.get_stream_monitoring_policy("stream-backyard-feeder")
            assert policy is not None
            assert policy.mode.value == "armed", "restored policy is durable truth -- must survive unchanged"

            with restored_repository.session_factory() as session:
                checkpoint = session.get(StreamRuntimeCheckpointModel, "stream-backyard-feeder")
                assert checkpoint is not None
                assert checkpoint.safety_hold_active is True
                assert checkpoint.last_stop_reason == "restore_hold"

            # The hold is a real, persisted DB row -- simulate the next
            # application restart by reopening the repository and reading it
            # back fresh, rather than trusting in-memory state.
            transaction.commit()
        finally:
            restored_repository.close()

        reopened = _repository(root)
        try:
            with reopened.session_factory() as session:
                checkpoint = session.get(StreamRuntimeCheckpointModel, "stream-backyard-feeder")
                assert checkpoint is not None
                assert checkpoint.safety_hold_active is True, (
                    "the hold must survive an application restart, not only the current process"
                )
        finally:
            reopened.close()


def test_restore_hold_does_not_affect_a_stream_that_was_never_armed() -> None:
    """Negative control: a Stream whose policy is `off` at backup time has
    nothing to hold -- `apply_restore_hold` must not touch it."""

    with TemporaryDirectory(dir="/tmp") as temporary_directory:
        root = Path(temporary_directory)
        repository = _repository(root)
        manager = _manager(repository, root)
        backup = manager.create_backup()
        repository.close()

        transaction = manager.replace_live_files(manager.verify_backup(backup.backup.id))
        restored_repository = _repository(root)
        restored_repository.prepare_for_supervision("local-backup-restore")
        restored_repository.apply_restore_hold()
        try:
            with restored_repository.session_factory() as session:
                checkpoint = session.get(StreamRuntimeCheckpointModel, "stream-backyard-feeder")
                assert checkpoint is not None
                assert checkpoint.safety_hold_active is False
                assert checkpoint.last_stop_reason != "restore_hold"
            transaction.commit()
        finally:
            restored_repository.close()
