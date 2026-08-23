from __future__ import annotations

import asyncio
import hashlib
import httpx
import json
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
import zipfile

import pytest

from mockingbird.api.main import app
from mockingbird.api.main import configure_repository
from mockingbird.repository.product_repository import SourceProviderConfigurationModel
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.backup import LocalBackupConflictError
from mockingbird.storage.backup import LocalBackupManager
from mockingbird.storage.backup import LocalBackupValidationError
from mockingbird.storage.backup import BACKUP_ROOT_ENV_VAR
from mockingbird.storage.backup import _archive_relative_for_managed_path
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION
from mockingbird.storage.models import MediaAssetModel
from mockingbird.storage.models import ReviewLabelModel
from mockingbird.storage.models import VisitModel
from tests.conftest import LegacyAuthenticatedTestClient


WINDOWS_DATABASE_PATH = r"C:\Users\Example User\MockingBird\data\mockingbird.sqlite3"
WINDOWS_MEDIA_ROOT = r"C:\Users\Example User\MockingBird\data\media\imports"
WINDOWS_STORED_MEDIA_PATH = "data\\media\\imports\\Nested Folder\\\u00c9lan bird.jpg"
ARCHIVE_RELATIVE_PATH = "Nested Folder/\u00c9lan bird.jpg"


def _api_request(method: str, path: str, **kwargs) -> httpx.Response:
    # These calls hit Administrator-tier backup/restore endpoints (see
    # `mockingbird.api.auth.ROUTE_POLICY`) -- `LegacyAuthenticatedTestClient`
    # signs in for real so the *business-rule* rejection this module tests
    # (a cross-install archive's restore is refused, no side effect) is what
    # actually gets exercised, rather than a 401 from never having signed in.
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with LegacyAuthenticatedTestClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def _repository(root: Path) -> ProductRepository:
    return ProductRepository(
        db_url=f"sqlite:///{root / 'mockingbird.sqlite3'}",
        media_root=root / "media" / "imports",
        classifier_manifest_export_root=root / "classifier-exports",
    )


def _rewrite_as_windows_backup(archive_path: Path, work_root: Path) -> None:
    with zipfile.ZipFile(archive_path, mode="r") as archive:
        members = {info.filename: archive.read(info) for info in archive.infolist()}
    manifest = json.loads(members["manifest.json"])
    database_path = work_root / "archive-database.sqlite3"
    database_path.write_bytes(members["database.sqlite3"])
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE media_assets SET local_path = ? WHERE id = ?",
            (WINDOWS_STORED_MEDIA_PATH, "media-cross-install"),
        )
        connection.execute(
            "UPDATE visits SET representative_media_path = ? WHERE id = ?",
            (WINDOWS_STORED_MEDIA_PATH, "visit-bird-feeder-001"),
        )
        connection.commit()
    database_bytes = database_path.read_bytes()
    manifest["source_layout"] = {
        "database_path": WINDOWS_DATABASE_PATH,
        "media_root": WINDOWS_MEDIA_ROOT,
    }
    manifest["database"]["size_bytes"] = len(database_bytes)
    manifest["database"]["sha256"] = hashlib.sha256(database_bytes).hexdigest()
    members["database.sqlite3"] = database_bytes
    members["manifest.json"] = json.dumps(
        manifest,
        indent=2,
        sort_keys=True,
    ).encode("utf-8")
    with zipfile.ZipFile(
        archive_path,
        mode="w",
        compression=zipfile.ZIP_STORED,
        allowZip64=True,
    ) as archive:
        for name, content in members.items():
            archive.writestr(name, content, compress_type=zipfile.ZIP_STORED)


def _cross_install_backup(tmp_path: Path):
    source_root = tmp_path / "source installation"
    source = _repository(source_root)
    media_path = source.media_root / "Nested Folder" / "\u00c9lan bird.jpg"
    media_path.parent.mkdir(parents=True)
    media_content = b"portable managed bird evidence"
    media_path.write_bytes(media_content)
    external_config = {
        "demo_seed": "backyard-demo",
        "ffmpeg_binary_path": r"C:\Tools\ffmpeg\ffmpeg.exe",
        "folder_path": r"D:\Trail Camera\Card 1",
        "live_stream_url": "rtsp://camera.local/live",
    }
    with source.engine.begin() as connection:
        connection.execute(
            MediaAssetModel.__table__.insert().values(
                id="media-cross-install",
                source_id="source-backyard-demo",
                stream_id="stream-backyard-feeder",
                filename=media_path.name,
                content_type="image/jpeg",
                media_type="image",
                local_path=str(media_path),
                original_filename=media_path.name,
                file_size_bytes=len(media_content),
                created_at=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
                notes="Managed cross-install fixture.",
            )
        )
        connection.execute(
            VisitModel.__table__.update()
            .where(VisitModel.id == "visit-bird-feeder-001")
            .values(representative_media_path=str(media_path))
        )
        connection.execute(
            SourceProviderConfigurationModel.__table__.insert().values(
                source_id="source-backyard-demo",
                provider_key="demo",
                config_json=json.dumps(external_config, sort_keys=True),
                updated_at=datetime(2026, 7, 17, 12, 0, tzinfo=UTC),
            )
        )
    source_manager = LocalBackupManager(
        db_url=source.db_url,
        media_root=source.media_root,
        backup_root=tmp_path / "backups",
    )
    created = source_manager.create_backup()
    source.close()
    _rewrite_as_windows_backup(created.backup.archive_path, tmp_path)

    target_root = tmp_path / "target installation"
    target = _repository(target_root)
    target_db_path = target_root / "mockingbird.sqlite3"
    target_db_before = hashlib.sha256(target_db_path.read_bytes()).hexdigest()
    target.close()
    target_manager = LocalBackupManager(
        db_url=f"sqlite:///{target_db_path}",
        media_root=target_root / "media" / "imports",
        backup_root=tmp_path / "backups",
    )
    verified = target_manager.verify_backup(created.backup.id)
    return (
        target_manager,
        verified,
        target_root,
        target_db_before,
        media_content,
        external_config,
    )


def test_cross_install_dry_run_and_restore_rebind_only_managed_storage(
    tmp_path: Path,
) -> None:
    (
        manager,
        verified,
        target_root,
        target_db_before,
        media_content,
        external_config,
    ) = _cross_install_backup(tmp_path)

    assert verified.backup.restore_compatible is False
    with pytest.raises(
        LocalBackupConflictError, match="backup_storage_layout_mismatch"
    ):
        manager.create_restore_plan(verified)

    plan = manager.create_restore_plan(verified, rebind_managed_storage=True)

    assert plan.restore_allowed is True
    assert plan.dry_run is True
    assert plan.confirmed is False
    assert plan.database_schema_version == CURRENT_DATABASE_SCHEMA_VERSION
    assert plan.media_archive_entry_count == 1
    assert plan.managed_database_reference_count == 2
    assert plan.external_paths_preserved == (
        "source_provider_configurations.demo.ffmpeg_binary_path",
        "source_provider_configurations.demo.folder_path",
        "source_provider_configurations.demo.live_stream_url",
    )
    assert plan.unsafe_paths == ()
    assert plan.collisions == ()
    assert plan.expected_entity_counts["media_assets"] == 1
    assert hashlib.sha256(
        (target_root / "mockingbird.sqlite3").read_bytes()
    ).hexdigest() == (target_db_before)
    assert not (target_root / "media" / "imports").exists()

    transaction = manager.replace_live_files(
        verified,
        rebind_managed_storage=True,
        plan=plan,
    )
    restored = _repository(target_root)
    try:
        with restored.engine.connect() as connection:
            media = (
                connection.execute(
                    MediaAssetModel.__table__.select().where(
                        MediaAssetModel.id == "media-cross-install"
                    )
                )
                .mappings()
                .one()
            )
            visit_path = (
                connection.execute(
                    VisitModel.__table__.select().where(
                        VisitModel.id == "visit-bird-feeder-001"
                    )
                )
                .mappings()
                .one()["representative_media_path"]
            )
            restored_config = (
                connection.execute(
                    SourceProviderConfigurationModel.__table__.select().where(
                        SourceProviderConfigurationModel.source_id
                        == "source-backyard-demo"
                    )
                )
                .mappings()
                .one()["config_json"]
            )
            review_ids = (
                connection.execute(
                    ReviewLabelModel.__table__.select().with_only_columns(
                        ReviewLabelModel.id
                    )
                )
                .scalars()
                .all()
            )
        expected_media_path = (
            target_root / "media" / "imports" / "Nested Folder" / "\u00c9lan bird.jpg"
        ).resolve()
        assert Path(media["local_path"]) == expected_media_path
        assert Path(visit_path) == expected_media_path
        assert expected_media_path.read_bytes() == media_content
        assert json.loads(restored_config) == external_config
        assert review_ids == ["review-label-squirrel-001"]
        assert len(review_ids) == plan.expected_entity_counts["review_labels"]
        assert restored.schema_status.integrity_check == "ok"
        transaction.commit()
    finally:
        restored.close()


def test_restore_plan_api_is_explicit_read_only_and_redacted(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, verified, target_root, _target_db_before_setup, *_rest = _cross_install_backup(
        tmp_path
    )
    monkeypatch.setenv(BACKUP_ROOT_ENV_VAR, str(manager.backup_root))
    repository = _repository(target_root)
    configure_repository(repository)
    try:
        # This test asserts the final `restore` call below has no side
        # effect on the database beyond its own rejection -- so, unlike
        # `_api_request` (a fresh client, and thus a fresh real sign-in,
        # per call), every request here reuses *one*
        # `LegacyAuthenticatedTestClient` and its one session. Re-signing
        # in per call would itself be a real write (a new session row)
        # that would otherwise be misread as a side effect of the restore
        # call actually under test. The two `restore-plan` calls are
        # exercised first, on their own dedicated client, so that minting
        # the shared session (on this test's own client's first request,
        # below) is not itself mistaken for a `restore-plan` side effect
        # either -- `restore-plan` is asserted `dry_run`/read-only in its
        # own right, so any of its own writes should still show up here.
        default_plan = _api_request(
            "POST",
            f"/api/settings/backups/{verified.backup.id}/restore-plan",
            json={"rebind_managed_storage": False},
        )
        assert default_plan.status_code == 409

        response = _api_request(
            "POST",
            f"/api/settings/backups/{verified.backup.id}/restore-plan",
            json={"rebind_managed_storage": True},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["backup_valid"] is True
        assert body["dry_run"] is True
        assert body["confirmed"] is False
        assert body["restore_allowed"] is True
        assert body["managed_database_reference_count"] == 2
        assert body["media_archive_entry_count"] == 1
        assert body["source_database_layout"] == {
            "platform": "windows",
            "absolute": True,
            "leaf_name": "mockingbird.sqlite3",
        }
        assert "Example User" not in response.text
        assert str(target_root) not in response.text

        async def restore_on_a_fresh_session() -> tuple[httpx.Response, str]:
            transport = httpx.ASGITransport(app=app)
            async with LegacyAuthenticatedTestClient(
                transport=transport, base_url="http://testserver"
            ) as client:
                # Mint this call's own session first (its first request,
                # whatever it is) so `target_db_before` below reflects every
                # write that will ever happen on this client except the
                # `restore` call itself.
                await client.get("/api/setup/state")
                before = hashlib.sha256(
                    (target_root / "mockingbird.sqlite3").read_bytes()
                ).hexdigest()
                restore_response = await client.post(
                    f"/api/settings/backups/{verified.backup.id}/restore",
                    json={"confirm": True, "rebind_managed_storage": False},
                )
            return restore_response, before

        default_restore, target_db_before = asyncio.run(restore_on_a_fresh_session())
        assert default_restore.status_code == 409
        assert (
            hashlib.sha256(
                (target_root / "mockingbird.sqlite3").read_bytes()
            ).hexdigest()
            == target_db_before
        )
        assert not (target_root / "media" / "imports").exists()
        assert len(manager.list_backups().backups) == 1
    finally:
        configure_repository(None)


def test_windows_managed_paths_use_root_relative_archive_identity() -> None:
    assert (
        _archive_relative_for_managed_path(
            "c:/USERS/Example User/MockingBird/data\\media/imports/Nested Folder/\u00c9lan bird.jpg",
            source_media_root=WINDOWS_MEDIA_ROOT,
            archive_relative_paths=[ARCHIVE_RELATIVE_PATH],
        )
        == ARCHIVE_RELATIVE_PATH
    )
    assert (
        _archive_relative_for_managed_path(
            WINDOWS_STORED_MEDIA_PATH,
            source_media_root=r"D:\Other Install\data\media\imports",
            archive_relative_paths=[ARCHIVE_RELATIVE_PATH],
        )
        == ARCHIVE_RELATIVE_PATH
    )


@pytest.mark.parametrize(
    "value",
    [
        "C:\\Outside\\\u00c9lan bird.jpg",
        "D:\\Users\\Example User\\MockingBird\\data\\media\\imports\\Nested Folder\\\u00c9lan bird.jpg",
        "data\\media\\imports\\..\\\u00c9lan bird.jpg",
        "\\Nested Folder\\\u00c9lan bird.jpg",
    ],
)
def test_windows_managed_paths_reject_escape_and_injection(value: str) -> None:
    with pytest.raises(LocalBackupValidationError):
        _archive_relative_for_managed_path(
            value,
            source_media_root=WINDOWS_MEDIA_ROOT,
            archive_relative_paths=[ARCHIVE_RELATIVE_PATH],
        )


def test_cross_install_plan_rejects_missing_managed_archive_identity(
    tmp_path: Path,
) -> None:
    manager, verified, *_rest = _cross_install_backup(tmp_path)
    archive_path = verified.backup.archive_path
    with zipfile.ZipFile(archive_path, mode="r") as archive:
        members = {info.filename: archive.read(info) for info in archive.infolist()}
    database_path = tmp_path / "missing-reference.sqlite3"
    database_path.write_bytes(members["database.sqlite3"])
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE media_assets SET local_path = ? WHERE id = ?",
            (r"data\media\imports\missing.jpg", "media-cross-install"),
        )
        connection.commit()
    database_bytes = database_path.read_bytes()
    manifest = json.loads(members["manifest.json"])
    manifest["database"]["size_bytes"] = len(database_bytes)
    manifest["database"]["sha256"] = hashlib.sha256(database_bytes).hexdigest()
    members["database.sqlite3"] = database_bytes
    members["manifest.json"] = json.dumps(manifest, sort_keys=True).encode("utf-8")
    with zipfile.ZipFile(
        archive_path, mode="w", compression=zipfile.ZIP_STORED
    ) as archive:
        for name, content in members.items():
            archive.writestr(name, content, compress_type=zipfile.ZIP_STORED)

    changed = manager.verify_backup(verified.backup.id)
    plan = manager.create_restore_plan(changed, rebind_managed_storage=True)

    assert plan.restore_allowed is False
    assert "media_assets.media-cross-install.local_path" in plan.unsafe_paths


def test_cross_install_plan_rejects_target_symlink_components(tmp_path: Path) -> None:
    manager, verified, target_root, *_rest = _cross_install_backup(tmp_path)
    real_media = tmp_path / "real-media"
    real_media.mkdir()
    configured_media = target_root / "linked-media"
    configured_media.symlink_to(real_media, target_is_directory=True)
    symlink_manager = LocalBackupManager(
        db_url=f"sqlite:///{target_root / 'mockingbird.sqlite3'}",
        media_root=configured_media,
        backup_root=manager.backup_root,
    )
    symlink_verified = symlink_manager.verify_backup(verified.backup.id)

    plan = symlink_manager.create_restore_plan(
        symlink_verified,
        rebind_managed_storage=True,
    )

    assert plan.restore_allowed is False
    assert "target.media_root_symlink" in plan.unsafe_paths
