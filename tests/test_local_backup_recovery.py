from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
import zipfile

import httpx
import pytest

from mockingbird.api import main as api_main
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
)


class ASGITestClient:
    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        async def send() -> httpx.Response:
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://testserver",
            ) as client:
                return await client.request(method, path, **kwargs)

        return asyncio.run(send())

    def get(self, path: str, **kwargs) -> httpx.Response:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> httpx.Response:
        return self.request("POST", path, **kwargs)


client = ASGITestClient()


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
    assert list_response.json()["backups"][0]["verification_status"] == "not_checked"

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
