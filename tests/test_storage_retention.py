import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

import pytest
from sqlalchemy import func, select

from mockingbird.api.schemas import (
    FolderImportCreate,
    LabelCategory,
    StorageCleanupExecuteRequest,
    StorageCleanupPurgeRequest,
    StorageCleanupRestoreRequest,
    StorageRetentionFrequency,
    StorageRetentionSettingsUpdate,
)
from mockingbird.observation.contracts import CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE
from mockingbird.repository.product_repository import (
    MAX_STORAGE_CLEANUP_HISTORY_ITEMS,
    MotionEvidenceModel,
    ProductRepository,
)
from mockingbird.storage.backup import LocalBackupManager
from mockingbird.storage.models import (
    EventModel,
    MediaAssetModel,
    ReviewLabelModel,
    StorageCleanupBatchModel,
    StorageCleanupItemModel,
    StorageRetentionSettingsModel,
    StreamModel,
    TaxonomyLabelModel,
    VisitEvidenceLinkModel,
    VisitModel,
)
from mockingbird.wildlife_taxonomy import is_wildlife_category


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    product_repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    yield product_repository
    product_repository.close()


def _add_media(
    repository: ProductRepository,
    *,
    media_id: str,
    age_days: int = 45,
    size_bytes: int = 64,
) -> Path:
    path = repository.media_root / f"{media_id}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size_bytes)
    with repository.session_factory() as session:
        with session.begin():
            stream = session.scalar(select(StreamModel).order_by(StreamModel.id))
            assert stream is not None
            session.add(
                MediaAssetModel(
                    id=media_id,
                    source_id=stream.source_id,
                    stream_id=stream.id,
                    filename=path.name,
                    content_type="application/octet-stream",
                    media_type="image",
                    local_path=str(path),
                    original_filename=path.name,
                    file_size_bytes=size_bytes,
                    created_at=datetime.now(UTC) - timedelta(days=age_days),
                    notes="retention test media",
                )
            )
    return path


def _settings_payload(key: str, **overrides: object) -> StorageRetentionSettingsUpdate:
    values: dict[str, object] = {
        "automatic_cleanup_enabled": False,
        "cleanup_frequency": StorageRetentionFrequency.weekly,
        "retain_unresolved_visit_evidence": True,
        "retain_reviewed_bird_wildlife_evidence": True,
        "reviewed_non_bird_age_days": 180,
        "superseded_evidence_age_days": 90,
        "orphaned_media_age_days": 30,
        "maximum_managed_media_bytes": None,
        "idempotency_key": key,
    }
    values.update(overrides)
    return StorageRetentionSettingsUpdate(**values)


def _add_active_visit_with_evidence(
    repository: ProductRepository,
    *,
    visit_id: str,
    evidence: list[tuple[str, bool]],
    review_status: str,
    reviewed_label: str | None,
    evidence_roles: dict[str, str] | None = None,
) -> None:
    now = datetime.now(UTC)
    roles = evidence_roles or {}
    with repository.session_factory() as session:
        with session.begin():
            assets = [session.get(MediaAssetModel, media_id) for media_id, _primary in evidence]
            assert all(asset is not None for asset in assets)
            primary_asset = next(
                (asset for asset, (_media_id, is_primary) in zip(assets, evidence) if is_primary),
                None,
            )
            first_asset = assets[0]
            assert first_asset is not None
            event = EventModel(
                id=f"{visit_id}-event",
                stream_id=first_asset.stream_id,
                title="Retention safety activity",
                event_type="activity",
                started_at=now,
                ended_at=now,
                primary_zone_id=None,
                review_status=review_status,
            )
            visit = VisitModel(
                id=visit_id,
                event_id=event.id,
                subject_label=reviewed_label or "unknown",
                species_guess=None,
                confidence=None,
                reviewed_label=reviewed_label,
                review_status=review_status,
                representative_media_path=primary_asset.local_path if primary_asset else None,
                zone_id=None,
                is_superseded=False,
            )
            session.add_all((event, visit))
            for index, ((media_id, is_primary), asset) in enumerate(zip(evidence, assets)):
                assert asset is not None
                session.add(
                    VisitEvidenceLinkModel(
                        id=f"{visit_id}-link-{index}",
                        visit_id=visit.id,
                        media_asset_id=media_id,
                        captured_at=now,
                        frame_sequence=index,
                        sort_order=index,
                        is_primary=is_primary,
                        evidence_role=roles.get(media_id, "monitoring_frame"),
                        created_at=now,
                    )
                )


def _create_imported_visit(
    repository: ProductRepository,
    *,
    label: str,
    folder: bool = False,
    tmp_path: Path | None = None,
) -> tuple[str, str, Path]:
    """Create a real manually- or folder-imported Visit through the actual
    product import path (never hand-constructed) -- Defect 1's fix must be
    proven against the real `create_media_import`/`import_folder_media` code
    path, not a synthetic shortcut. Returns
    (visit_id, media_asset_id, file_path)."""

    if folder:
        assert tmp_path is not None
        source_folder = tmp_path / f"{label}-folder"
        source_folder.mkdir(exist_ok=True)
        (source_folder / f"{label}.jpg").write_bytes(f"folder-import-bytes-{label}".encode())
        result = repository.import_folder_media(
            FolderImportCreate(folder_path=str(source_folder), subject_label="unknown_bird")
        )
        assert result.imported_count == 1
        visit, asset = result.visits[0], result.media_assets[0]
    else:
        result = repository.create_media_import(
            content=f"manual-import-bytes-{label}".encode(),
            original_filename=f"{label}.jpg",
            content_type="image/jpeg",
            subject_label="unknown_bird",
        )
        visit, asset = result.visit, result.media_asset
    return visit.id, asset.id, Path(asset.local_path)


def test_default_storage_retention_read_is_safe_off_and_does_not_persist_policy(
    repository: ProductRepository,
) -> None:
    with repository.session_factory() as session:
        assert session.scalar(select(func.count(StorageRetentionSettingsModel.singleton_id))) == 0

    settings = repository.storage_retention_settings()

    assert settings.automatic_cleanup_enabled is False
    assert settings.persisted is False
    assert settings.recommended_defaults is True
    with repository.session_factory() as session:
        assert session.scalar(select(func.count(StorageRetentionSettingsModel.singleton_id))) == 0


def test_storage_schema_initialization_leaves_existing_managed_files_untouched(
    tmp_path: Path,
) -> None:
    media_root = tmp_path / "media"
    existing_path = media_root / "existing-before-retention.bin"
    existing_path.parent.mkdir(parents=True, exist_ok=True)
    existing_path.write_bytes(b"preexisting-media")

    initialized = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'migration.sqlite3'}",
        media_root=media_root,
    )
    try:
        assert initialized.schema_status.current_version >= 11
        assert existing_path.read_bytes() == b"preexisting-media"
    finally:
        initialized.close()


def test_preview_stale_recovery_restore_and_idempotent_settings(
    repository: ProductRepository,
) -> None:
    first_path = _add_media(repository, media_id="retention-orphan-old", age_days=50)
    settings, already_applied = repository.update_storage_retention_settings(
        _settings_payload("retention-settings-one")
    )
    repeated, repeated_applied = repository.update_storage_retention_settings(
        _settings_payload("retention-settings-one")
    )
    assert already_applied is False
    assert repeated_applied is True
    assert repeated.policy_revision == settings.policy_revision

    stale_preview = repository.preview_storage_cleanup()
    _add_media(repository, media_id="retention-orphan-new", age_days=45)
    with pytest.raises(ValueError, match="storage_cleanup_preview_stale"):
        repository.execute_storage_cleanup(
            StorageCleanupExecuteRequest(
                preview_token=stale_preview.preview_token,
                confirm=True,
                idempotency_key="retention-stale-cleanup",
            )
        )
    assert first_path.exists()

    preview = repository.preview_storage_cleanup()
    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-cleanup-one",
        )
    )
    assert result.state == "quarantined"
    assert not first_path.exists()
    assert repository.storage_cleanup_history().items[0].can_restore is True
    repeated_cleanup = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-cleanup-one",
        )
    )
    assert repeated_cleanup.idempotent is True

    restored = repository.restore_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupRestoreRequest(idempotency_key="retention-restore-one"),
    )
    assert restored is not None and restored.state == "restored"
    assert first_path.exists()
    repeated_restore = repository.restore_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupRestoreRequest(idempotency_key="retention-restore-one"),
    )
    assert repeated_restore is not None and repeated_restore.idempotent is True


def test_parent_still_is_protected_while_a_derived_activity_crop_exists(
    repository: ProductRepository,
) -> None:
    parent_path = _add_media(
        repository,
        media_id="retention-high-resolution-original",
        age_days=365,
    )
    crop_path = _add_media(
        repository,
        media_id="retention-activity-crop",
        age_days=365,
    )
    with repository.session_factory() as session:
        with session.begin():
            parent = session.get(MediaAssetModel, "retention-high-resolution-original")
            crop = session.get(MediaAssetModel, "retention-activity-crop")
            assert parent is not None and crop is not None
            parent.evidence_role = "high_resolution_original"
            crop.parent_media_asset_id = parent.id
            crop.evidence_role = "activity_crop"

    preview = repository.preview_storage_cleanup()

    eligible = {item.category: item.media_count for item in preview.categories}
    protected = {item.category for item in preview.protected_counts}
    assert preview.eligible_media_count == 1
    assert eligible == {"orphaned_managed_media": 1}
    assert "derived_media_reference" in protected
    assert parent_path.exists()
    assert crop_path.exists()


def test_refined_crop_history_is_protected_even_when_it_is_not_primary(
    repository: ProductRepository,
) -> None:
    _add_media(repository, media_id="retention-refined-parent", age_days=365)
    _add_media(repository, media_id="retention-refined-automatic", age_days=365)
    _add_media(repository, media_id="retention-refined-user", age_days=365)
    with repository.session_factory() as session:
        with session.begin():
            parent = session.get(MediaAssetModel, "retention-refined-parent")
            automatic = session.get(MediaAssetModel, "retention-refined-automatic")
            refined = session.get(MediaAssetModel, "retention-refined-user")
            assert parent is not None and automatic is not None and refined is not None
            parent.evidence_role = "high_resolution_original"
            automatic.parent_media_asset_id = parent.id
            automatic.evidence_role = "activity_crop"
            refined.parent_media_asset_id = parent.id
            refined.evidence_role = "user_refined_crop"
            refined.derivation_source = "user_refined_crop"

    _add_active_visit_with_evidence(
        repository,
        visit_id="retention-refined-history-visit",
        evidence=[
            ("retention-refined-parent", False),
            ("retention-refined-automatic", True),
            ("retention-refined-user", False),
        ],
        review_status="reviewed",
        reviewed_label="false_positive",
    )
    repository.update_storage_retention_settings(
        _settings_payload(
            "retention-refined-history-settings",
            retain_reviewed_bird_wildlife_evidence=False,
            reviewed_non_bird_age_days=30,
        )
    )

    preview = repository.preview_storage_cleanup()

    protected = {item.category: item.media_count for item in preview.protected_counts}
    assert preview.eligible_media_count == 0
    assert protected["crop_revision_history"] == 2
    assert protected["derived_media_reference"] == 1


def test_interrupted_move_remains_recoverable_without_removing_links(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_path = _add_media(repository, media_id="retention-interrupted-move", age_days=365)
    preview = repository.preview_storage_cleanup()
    real_move = repository._move_storage_item_to_recovery

    def move_then_interrupt(item: StorageCleanupItemModel) -> bool:
        assert real_move(item)
        raise OSError("simulated interruption after recovery move")

    monkeypatch.setattr(repository, "_move_storage_item_to_recovery", move_then_interrupt)
    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-interrupted-move",
        )
    )

    assert result.state == "staging"
    assert not original_path.exists()
    assert repository.storage_cleanup_history().items[0].can_restore is True
    restored = repository.restore_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupRestoreRequest(idempotency_key="retention-interrupted-move-restore"),
    )
    assert restored is not None and restored.state == "restored"
    assert original_path.exists()


def test_active_unresolved_visit_evidence_is_protected_and_summarized(
    repository: ProductRepository,
) -> None:
    media_id = "retention-unresolved-primary"
    path = _add_media(repository, media_id=media_id, age_days=365)
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            asset = session.get(MediaAssetModel, media_id)
            assert asset is not None
            event = EventModel(
                id="retention-unresolved-event",
                stream_id=asset.stream_id,
                title="Unresolved outdoor activity",
                event_type="activity",
                started_at=now,
                ended_at=now,
                primary_zone_id=None,
                review_status="needs_review",
            )
            visit = VisitModel(
                id="retention-unresolved-visit",
                event_id=event.id,
                subject_label="unknown",
                species_guess=None,
                confidence=None,
                reviewed_label=None,
                review_status="needs_review",
                representative_media_path=str(path),
                zone_id=None,
                is_superseded=False,
            )
            session.add_all((event, visit))
            session.add(
                VisitEvidenceLinkModel(
                    id="retention-unresolved-link",
                    visit_id=visit.id,
                    media_asset_id=asset.id,
                    captured_at=now,
                    frame_sequence=None,
                    sort_order=0,
                    is_primary=True,
                    created_at=now,
                )
            )

    summary = repository.storage_summary()
    preview = repository.preview_storage_cleanup()

    assert summary.active_visit_media_count == 1
    assert summary.unresolved_visit_evidence_count == 1
    assert preview.eligible_media_count == 0
    assert any(item.category == "unresolved_visit_evidence" for item in preview.protected_counts)
    assert path.exists()


def test_unresolved_secondary_evidence_is_always_protected(
    repository: ProductRepository,
) -> None:
    _add_media(repository, media_id="retention-unresolved-primary", age_days=365)
    secondary_path = _add_media(repository, media_id="retention-unresolved-secondary", age_days=365)
    _add_active_visit_with_evidence(
        repository,
        visit_id="retention-unresolved-secondary-visit",
        evidence=[
            ("retention-unresolved-primary", True),
            ("retention-unresolved-secondary", False),
        ],
        review_status="needs_review",
        reviewed_label=None,
    )
    repository.update_storage_retention_settings(
        _settings_payload("retention-unresolved-policy", retain_unresolved_visit_evidence=False)
    )

    preview = repository.preview_storage_cleanup()

    assert preview.eligible_media_count == 0
    assert any(item.category == "unresolved_visit_evidence" for item in preview.protected_counts)
    assert secondary_path.exists()


def _add_rejected_analysis_media(
    repository: ProductRepository, *, media_id: str, age_days: int
) -> Path:
    """A MediaAsset referenced only by a rejected/suppressed detection
    record (never a Visit) -- the `linked_evidence_or_analysis` category.
    Appliance / Storage / Privacy / Recovery v1, Phase B/D: previously
    untested entirely (this category had no lever and was invisible in
    `StorageSummary`)."""

    path = _add_media(repository, media_id=media_id, age_days=age_days)
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            asset = session.get(MediaAssetModel, media_id)
            assert asset is not None
            session.add(
                MotionEvidenceModel(
                    id=f"{media_id}-evidence",
                    source_id=asset.source_id,
                    stream_id=asset.stream_id,
                    zone_id=None,
                    start_frame_index=None,
                    end_frame_index=None,
                    best_frame_index=None,
                    start_time=None,
                    end_time=None,
                    best_frame_time=None,
                    peak_changed_ratio=0.1,
                    triggered_frame_count=1,
                    scoring_config_json="{}",
                    snapshot_media_asset_id=media_id,
                    status="rejected",
                    promoted_event_id=None,
                    promoted_visit_id=None,
                    created_at=now,
                    notes=None,
                )
            )
    return path


def test_linked_evidence_or_analysis_is_visible_in_storage_summary(
    repository: ProductRepository,
) -> None:
    _add_rejected_analysis_media(repository, media_id="retention-rejected-analysis", age_days=365)

    summary = repository.storage_summary()

    assert summary.linked_evidence_or_analysis_count == 1
    assert summary.linked_evidence_or_analysis_bytes > 0


def test_linked_evidence_or_analysis_is_protected_forever_by_default(
    repository: ProductRepository,
) -> None:
    """The default (`rejected_analysis_media_age_days=None`) must preserve
    every existing installation's exact behavior: protected forever, no
    matter how old."""

    path = _add_rejected_analysis_media(repository, media_id="retention-rejected-default", age_days=3650)

    preview = repository.preview_storage_cleanup()

    assert preview.eligible_media_count == 0
    assert any(item.category == "linked_evidence_or_analysis" for item in preview.protected_counts)
    assert path.exists()


def test_linked_evidence_or_analysis_becomes_eligible_only_after_explicit_opt_in(
    repository: ProductRepository,
) -> None:
    young_path = _add_rejected_analysis_media(repository, media_id="retention-rejected-young", age_days=5)
    old_path = _add_rejected_analysis_media(repository, media_id="retention-rejected-old", age_days=100)
    repository.update_storage_retention_settings(
        _settings_payload("retention-rejected-opt-in", rejected_analysis_media_age_days=30)
    )

    preview = repository.preview_storage_cleanup()

    assert preview.eligible_media_count == 1
    category = next(item for item in preview.categories if item.category == "rejected_analysis_media")
    assert category.media_count == 1
    # The young one must still show up as protected, not silently dropped.
    assert any(item.category == "linked_evidence_or_analysis" for item in preview.protected_counts)
    assert young_path.exists()
    assert old_path.exists()  # preview only -- nothing deleted yet


def test_reviewed_wildlife_secondary_evidence_follows_explicit_policy_without_changing_truth(
    repository: ProductRepository,
) -> None:
    primary_path = _add_media(repository, media_id="retention-bird-primary", age_days=365)
    secondary_path = _add_media(repository, media_id="retention-bird-secondary", age_days=365)
    _add_active_visit_with_evidence(
        repository,
        visit_id="retention-bird-visit",
        evidence=[("retention-bird-primary", True), ("retention-bird-secondary", False)],
        review_status="reviewed",
        reviewed_label="bird",
    )
    repository.update_storage_retention_settings(
        _settings_payload("retention-bird-protected", reviewed_non_bird_age_days=30)
    )
    protected_preview = repository.preview_storage_cleanup()
    assert protected_preview.eligible_media_count == 0
    assert any(
        item.category == "reviewed_bird_wildlife_evidence"
        for item in protected_preview.protected_counts
    )

    repository.update_storage_retention_settings(
        _settings_payload(
            "retention-bird-explicit-permission",
            retain_reviewed_bird_wildlife_evidence=False,
            reviewed_non_bird_age_days=30,
        )
    )
    preview = repository.preview_storage_cleanup()
    assert preview.eligible_media_count == 1
    assert any(item.category == "reviewed_bird_wildlife_secondary" for item in preview.categories)
    assert any("reduce secondary Visit evidence" in warning for warning in preview.warnings)
    with repository.session_factory() as session:
        truth_before = [
            (label.id, label.target_type, label.target_id, label.label, label.notes)
            for label in session.scalars(select(ReviewLabelModel).order_by(ReviewLabelModel.id))
        ]

    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-bird-cleanup",
        )
    )
    assert result.state == "quarantined"
    assert primary_path.exists()
    assert not secondary_path.exists()
    with repository.session_factory() as session:
        visit = session.get(VisitModel, "retention-bird-visit")
        assert visit is not None
        assert visit.review_status == "reviewed"
        assert visit.reviewed_label == "bird"
        assert session.scalar(
            select(func.count(VisitEvidenceLinkModel.id)).where(
                VisitEvidenceLinkModel.visit_id == visit.id
            )
        ) == 1
        truth_after = [
            (label.id, label.target_type, label.target_id, label.label, label.notes)
            for label in session.scalars(select(ReviewLabelModel).order_by(ReviewLabelModel.id))
        ]
    assert truth_after == truth_before


def test_shared_media_linked_to_a_protected_visit_is_never_eligible(
    repository: ProductRepository,
) -> None:
    _add_media(repository, media_id="retention-shared-protected-primary", age_days=365)
    _add_media(repository, media_id="retention-shared-reviewed-primary", age_days=365)
    shared_path = _add_media(repository, media_id="retention-shared-secondary", age_days=365)
    _add_active_visit_with_evidence(
        repository,
        visit_id="retention-shared-protected-visit",
        evidence=[
            ("retention-shared-protected-primary", True),
            ("retention-shared-secondary", False),
        ],
        review_status="needs_review",
        reviewed_label=None,
    )
    _add_active_visit_with_evidence(
        repository,
        visit_id="retention-shared-reviewed-visit",
        evidence=[
            ("retention-shared-reviewed-primary", True),
            ("retention-shared-secondary", False),
        ],
        review_status="reviewed",
        reviewed_label="non_bird",
    )
    repository.update_storage_retention_settings(
        _settings_payload(
            "retention-shared-policy",
            retain_unresolved_visit_evidence=False,
            reviewed_non_bird_age_days=30,
        )
    )

    preview = repository.preview_storage_cleanup()

    assert preview.eligible_media_count == 0
    assert any(item.category == "unresolved_visit_evidence" for item in preview.protected_counts)
    assert shared_path.exists()


def test_restore_conflict_preserves_unrelated_destination_file(
    repository: ProductRepository,
) -> None:
    original_path = _add_media(repository, media_id="retention-restore-conflict", age_days=365)
    preview = repository.preview_storage_cleanup()
    cleanup = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-restore-conflict-cleanup",
        )
    )
    original_path.write_bytes(b"unrelated-new-file")

    restored = repository.restore_storage_cleanup_batch(
        cleanup.batch_id,
        StorageCleanupRestoreRequest(idempotency_key="retention-restore-conflict"),
    )

    assert restored is not None and restored.state == "restore_conflict"
    assert original_path.read_bytes() == b"unrelated-new-file"
    assert restored.failed_count >= 1


def test_unmanaged_and_incomplete_media_are_never_eligible(
    repository: ProductRepository,
    tmp_path: Path,
) -> None:
    incomplete_path = _add_media(repository, media_id="retention-incomplete", age_days=365)
    outside_path = tmp_path / "outside-managed-media.bin"
    outside_path.write_bytes(b"outside")
    with repository.session_factory() as session:
        with session.begin():
            incomplete = session.get(MediaAssetModel, "retention-incomplete")
            stream = session.scalar(select(StreamModel).order_by(StreamModel.id))
            assert incomplete is not None and stream is not None
            incomplete.file_size_bytes += 1
            session.add(
                MediaAssetModel(
                    id="retention-outside",
                    source_id=stream.source_id,
                    stream_id=stream.id,
                    filename=outside_path.name,
                    content_type="application/octet-stream",
                    media_type="image",
                    local_path=str(outside_path),
                    original_filename=outside_path.name,
                    file_size_bytes=outside_path.stat().st_size,
                    created_at=datetime.now(UTC) - timedelta(days=365),
                    notes="outside storage must remain untouched",
                )
            )

    preview = repository.preview_storage_cleanup()

    assert preview.eligible_media_count == 0
    protected = {item.category for item in preview.protected_counts}
    assert "integrity_mismatch" in protected
    assert "outside_managed_storage" in protected
    assert incomplete_path.exists()
    assert outside_path.exists()


def test_purge_rejects_recoverable_media_and_then_purges_only_after_expiry(
    repository: ProductRepository,
) -> None:
    original_path = _add_media(repository, media_id="retention-purge", age_days=365)
    preview = repository.preview_storage_cleanup()
    cleanup = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-purge-cleanup",
        )
    )
    assert not original_path.exists()
    with pytest.raises(ValueError, match="storage_cleanup_recovery_active"):
        repository.purge_storage_cleanup_batch(
            cleanup.batch_id,
            StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-purge-early"),
        )
    with repository.session_factory() as session:
        with session.begin():
            batch = session.get(StorageCleanupBatchModel, cleanup.batch_id)
            assert batch is not None
            batch.recovery_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    purged = repository.purge_storage_cleanup_batch(
        cleanup.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-purge-expired"),
    )
    assert purged is not None and purged.state == "purged"
    assert purged.moved_to_recovery_count == 1
    repeated = repository.purge_storage_cleanup_batch(
        cleanup.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-purge-expired"),
    )
    assert repeated is not None and repeated.idempotent is True


def test_storage_target_removes_oldest_eligible_media_first(
    repository: ProductRepository,
) -> None:
    older_path = _add_media(
        repository,
        media_id="retention-target-older",
        age_days=60,
        size_bytes=1_048_576,
    )
    newer_path = _add_media(
        repository,
        media_id="retention-target-newer",
        age_days=45,
        size_bytes=1_048_576,
    )
    repository.update_storage_retention_settings(
        _settings_payload(
            "retention-target-settings",
            maximum_managed_media_bytes=1_048_576,
        )
    )

    preview = repository.preview_storage_cleanup()
    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-target-cleanup",
        )
    )

    assert preview.eligible_media_count == 1
    assert result.moved_to_recovery_count == 1
    assert not older_path.exists()
    assert newer_path.exists()


def test_storage_target_stops_at_protected_media_boundary(
    repository: ProductRepository,
) -> None:
    _add_media(
        repository,
        media_id="retention-protected-target-primary",
        age_days=365,
        size_bytes=1_048_577,
    )
    _add_active_visit_with_evidence(
        repository,
        visit_id="retention-protected-target-visit",
        evidence=[("retention-protected-target-primary", True)],
        review_status="needs_review",
        reviewed_label=None,
    )
    repository.update_storage_retention_settings(
        _settings_payload(
            "retention-protected-target-settings",
            maximum_managed_media_bytes=1_048_576,
        )
    )

    summary = repository.storage_summary()
    preview = repository.preview_storage_cleanup()

    assert preview.eligible_media_count == 0
    assert summary.storage_warning == (
        "Storage target could not be reached because protected evidence was retained."
    )


def test_complete_backup_includes_recoverable_media_and_metadata(
    repository: ProductRepository,
    tmp_path: Path,
) -> None:
    _add_media(repository, media_id="retention-backup-recovery", age_days=365)
    preview = repository.preview_storage_cleanup()
    cleanup = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-backup-recovery-cleanup",
        )
    )
    manager = LocalBackupManager(
        db_url=repository.db_url,
        media_root=repository.media_root,
        backup_root=tmp_path / "backups",
    )

    verification = manager.create_backup()

    assert verification.backup.database_schema_version >= 11
    with ZipFile(verification.backup.archive_path) as archive:
        names = archive.namelist()
    assert any(name.startswith(f"media/.recovery/{cleanup.batch_id}/") for name in names)


# --------------------------------------------------------------------------
# Same-Frame Species Evidence v1 (see docs/same-frame-species-evidence-
# contract.md): "Use existing media retention rules... do not create
# immortal classifier evidence accidentally."
# --------------------------------------------------------------------------


def test_same_frame_evidence_is_ordinary_secondary_evidence_not_immortal(
    repository: ProductRepository,
) -> None:
    """A `classifier_same_frame` asset gets no special protection beyond the
    ordinary non-primary-evidence rules every other secondary role already
    follows -- it is not permanently retained, and not silently deleted
    before those rules allow it either."""

    primary_path = _add_media(repository, media_id="retention-same-frame-primary", age_days=365)
    same_frame_path = _add_media(repository, media_id="retention-same-frame-secondary", age_days=365)
    _add_active_visit_with_evidence(
        repository,
        visit_id="retention-same-frame-visit",
        evidence=[
            ("retention-same-frame-primary", True),
            ("retention-same-frame-secondary", False),
        ],
        review_status="reviewed",
        reviewed_label="bird",
        evidence_roles={"retention-same-frame-secondary": CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE},
    )

    # Reviewed-wildlife protection ON (the conservative default): the
    # same-frame asset is protected for exactly the same "explicit policy"
    # reason a `context`/`alternate` secondary role already is -- not
    # because of anything role-specific to it.
    repository.update_storage_retention_settings(
        _settings_payload("retention-same-frame-protected", reviewed_non_bird_age_days=30)
    )
    protected_preview = repository.preview_storage_cleanup()
    assert protected_preview.eligible_media_count == 0
    assert any(
        item.category == "reviewed_bird_wildlife_evidence"
        for item in protected_preview.protected_counts
    )
    assert same_frame_path.exists()

    # Once that explicit policy is relaxed, the same-frame asset becomes an
    # ordinary cleanup candidate -- proving it is not accidentally immortal.
    repository.update_storage_retention_settings(
        _settings_payload(
            "retention-same-frame-explicit-permission",
            retain_reviewed_bird_wildlife_evidence=False,
            reviewed_non_bird_age_days=30,
        )
    )
    preview = repository.preview_storage_cleanup()
    assert preview.eligible_media_count == 1
    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-same-frame-cleanup",
        )
    )
    assert result.state == "quarantined"
    # Deletion preserves referential integrity: the primary evidence and the
    # Visit's own reviewed truth are both untouched by removing the
    # secondary classifier asset.
    assert primary_path.exists()
    assert not same_frame_path.exists()
    with repository.session_factory() as session:
        visit = session.get(VisitModel, "retention-same-frame-visit")
        assert visit is not None
        assert visit.review_status == "reviewed"
        assert visit.reviewed_label == "bird"
        remaining_links = session.scalars(
            select(VisitEvidenceLinkModel).where(
                VisitEvidenceLinkModel.visit_id == visit.id
            )
        ).all()
        assert len(remaining_links) == 1
        assert remaining_links[0].media_asset_id == "retention-same-frame-primary"


def test_storage_visit_is_wildlife_matches_the_shared_wildlife_taxonomy_predicate(
    repository: ProductRepository,
) -> None:
    """`_storage_visit_is_wildlife`'s taxonomy-matched branch now routes
    through the shared `wildlife_taxonomy.is_wildlife_category` denylist
    (see product_repository.py) instead of its own local
    `{"bird", "mammal"}` allowlist. This proves the retention check agrees
    with that shared predicate for every current `LabelCategory` -- not
    only the two values the old inline set happened to hardcode -- so a
    future wildlife category is protected from cleanup automatically
    rather than silently falling outside this guard. The untaxonomized
    fallback (no matching taxonomy row) is unrelated to this consolidation
    and is checked unchanged at the end.

    Wildlife Semantic Consistency v1 (see docs/wildlife-semantic-
    consistency-v1-contract.md): `"unknown"` is the one deliberate
    exception to "matches `is_wildlife_category` exactly" -- a reviewed
    "unknown_bird"/"unknown_animal"/"ambiguous" correction is confirmed
    wildlife presence for storage/retention purposes even though it is
    intentionally never a wildlife *taxon* for reporting purposes (see
    `is_wildlife_category`'s own docstring: callers needing this recognize
    it "through their own dedicated confirmed-but-unresolved handling,"
    which this retention check now is).
    """

    now = datetime.now(UTC)
    with repository.session_factory() as session:
        stream = session.scalar(select(StreamModel).order_by(StreamModel.id))
        assert stream is not None
        stream_id = stream.id

    cases = [
        ("test-wildlife-bird", LabelCategory.bird.value, True),
        ("test-wildlife-mammal", LabelCategory.mammal.value, True),
        ("test-wildlife-pet", LabelCategory.pet.value, False),
        ("test-wildlife-person", LabelCategory.person.value, False),
        ("test-wildlife-vehicle", LabelCategory.vehicle.value, False),
        ("test-wildlife-object", LabelCategory.object.value, False),
        ("test-wildlife-false-positive", LabelCategory.false_positive.value, False),
        # Confirmed wildlife presence, species honestly unresolved -- the
        # one deliberate divergence from `is_wildlife_category` itself
        # (which returns False for "unknown" by design). See the docstring
        # above.
        ("test-wildlife-unknown", LabelCategory.unknown.value, True),
    ]
    with repository.session_factory() as session:
        with session.begin():
            for label, category, _expected in cases:
                session.add(
                    TaxonomyLabelModel(
                        id=f"{label}-taxon",
                        label=label,
                        display_name=label,
                        category=category,
                        aliases_json="[]",
                        is_species=False,
                        is_reviewable=True,
                    )
                )
                session.add(
                    EventModel(
                        id=f"{label}-event",
                        stream_id=stream_id,
                        title="wildlife-taxonomy consolidation check",
                        event_type="activity",
                        started_at=now,
                        ended_at=now,
                        primary_zone_id=None,
                        review_status="reviewed",
                    )
                )
                session.add(
                    VisitModel(
                        id=f"{label}-visit",
                        event_id=f"{label}-event",
                        subject_label=label,
                        species_guess=None,
                        confidence=None,
                        reviewed_label=label,
                        review_status="reviewed",
                        representative_media_path=None,
                        zone_id=None,
                        is_superseded=False,
                    )
                )

    with repository.session_factory() as session:
        for label, category, expected in cases:
            visit = session.get(VisitModel, f"{label}-visit")
            assert visit is not None
            result = repository._storage_visit_is_wildlife(session, visit)
            assert result is expected, f"category={category} expected wildlife={expected}"
            # Agrees with the shared `is_wildlife_category` predicate for
            # every category except the one deliberate, documented
            # exception ("unknown" -- see this test's own docstring).
            assert result is (is_wildlife_category(category) or category == LabelCategory.unknown.value)

    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id="untaxonomized-event",
                    stream_id=stream_id,
                    title="untaxonomized fallback check",
                    event_type="activity",
                    started_at=now,
                    ended_at=now,
                    primary_zone_id=None,
                    review_status="reviewed",
                )
            )
            session.add(
                VisitModel(
                    id="untaxonomized-visit",
                    event_id="untaxonomized-event",
                    subject_label="wildlife",
                    species_guess=None,
                    confidence=None,
                    reviewed_label="wildlife",
                    review_status="reviewed",
                    representative_media_path=None,
                    zone_id=None,
                    is_superseded=False,
                )
            )
    with repository.session_factory() as session:
        visit = session.get(VisitModel, "untaxonomized-visit")
        assert visit is not None
        assert repository._storage_visit_is_wildlife(session, visit) is True


def test_newly_seeded_mammal_taxonomy_labels_are_wildlife_retention_protected(
    repository: ProductRepository,
) -> None:
    """Broader Wildlife Maturity v1: before the new taxonomy rows were
    seeded (docs/broader-wildlife-maturity-v1-contract.md P0 #2), a
    reviewed "deer"/"raccoon"/"opossum"/"fox"/"rabbit" correction had no
    matching `TaxonomyLabelModel` row and fell through to `_storage_visit_
    is_wildlife`'s untaxonomized fallback (`{"bird", "unknown_bird",
    "wildlife"}`), which does not include them -- so that evidence was not
    protected by "keep reviewed wildlife evidence" retention the way a
    confirmed bird or squirrel already was. This proves the real, seeded
    rows (not synthetic ones) now resolve through the taxonomy-matched
    branch and are protected, using the same demo taxonomy every
    repository actually seeds (`seed_if_empty` -> `_seed_taxonomy_labels`),
    not a hand-inserted row.
    """

    now = datetime.now(UTC)
    with repository.session_factory() as session:
        stream = session.scalar(select(StreamModel).order_by(StreamModel.id))
        assert stream is not None
        stream_id = stream.id

    newly_seeded_labels = ("deer", "raccoon", "opossum", "fox", "rabbit")
    with repository.session_factory() as session:
        with session.begin():
            for label in newly_seeded_labels:
                # No hand-inserted TaxonomyLabelModel row here -- this
                # relies entirely on seed_if_empty() having already run.
                session.add(
                    EventModel(
                        id=f"{label}-cohort-event",
                        stream_id=stream_id,
                        title="broader wildlife maturity retention check",
                        event_type="activity",
                        started_at=now,
                        ended_at=now,
                        primary_zone_id=None,
                        review_status="reviewed",
                    )
                )
                session.add(
                    VisitModel(
                        id=f"{label}-cohort-visit",
                        event_id=f"{label}-cohort-event",
                        subject_label="animal",
                        species_guess=None,
                        confidence=None,
                        reviewed_label=label,
                        review_status="reviewed",
                        representative_media_path=None,
                        zone_id=None,
                        is_superseded=False,
                    )
                )

    with repository.session_factory() as session:
        taxonomy_labels = {
            row.label: row
            for row in session.scalars(
                select(TaxonomyLabelModel).where(TaxonomyLabelModel.label.in_(newly_seeded_labels))
            ).all()
        }
        for label in newly_seeded_labels:
            taxonomy = taxonomy_labels.get(label)
            assert taxonomy is not None, f"{label} must already be a seeded taxonomy row"
            assert taxonomy.category == LabelCategory.mammal.value
            assert taxonomy.is_species is False
            visit = session.get(VisitModel, f"{label}-cohort-visit")
            assert visit is not None
            assert repository._storage_visit_is_wildlife(session, visit) is True, (
                f"{label} must be wildlife-retention-protected via its real seeded taxonomy row"
            )

    # Honest boundary check: a real mammal with genuinely no taxonomy row
    # (not one of the newly-seeded five, and not one of the untaxonomized
    # fallback's three literal strings) still is not retention-protected --
    # this milestone closes the specific cohort gap, not every conceivable
    # mammal a reviewer might type freeform. See the milestone's capability
    # matrix for the documented remaining gap.
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id="bobcat-unseeded-event",
                    stream_id=stream_id,
                    title="unseeded mammal boundary check",
                    event_type="activity",
                    started_at=now,
                    ended_at=now,
                    primary_zone_id=None,
                    review_status="reviewed",
                )
            )
            session.add(
                VisitModel(
                    id="bobcat-unseeded-visit",
                    event_id="bobcat-unseeded-event",
                    subject_label="animal",
                    species_guess=None,
                    confidence=None,
                    reviewed_label="bobcat",
                    review_status="reviewed",
                    representative_media_path=None,
                    zone_id=None,
                    is_superseded=False,
                )
            )
    with repository.session_factory() as session:
        visit = session.get(VisitModel, "bobcat-unseeded-visit")
        assert visit is not None
        assert repository._storage_visit_is_wildlife(session, visit) is False


# --- Retention Correctness & Bounded Cleanup Closure v1 --------------------
#
# Defect 1: imported/folder-imported media (no materialized
# VisitEvidenceLink -- see `_create_media_product_records`) is protected
# forever unconditionally by the `legacy_representative_evidence` bucket,
# contrary to docs/appliance-storage-privacy-recovery-v1-contract.md's own
# "same active/superseded/reviewed rules as any other Visit-linked evidence
# -- no separate contract." The fix makes it follow exactly that: protected
# forever while any referencing Visit remains active (mirroring
# active_visit_primary_evidence), eligible only once every referencing
# Visit is superseded and old enough (mirroring superseded_only_evidence).


def test_manual_imported_media_is_protected_while_visit_is_active(
    repository: ProductRepository,
) -> None:
    _visit_id, _asset_id, path = _create_imported_visit(repository, label="manual-active")

    preview = repository.preview_storage_cleanup()

    assert preview.eligible_media_count == 0
    protected = {item.category for item in preview.protected_counts}
    assert "legacy_representative_evidence" in protected
    assert path.exists()


def test_folder_imported_media_is_protected_while_visit_is_active(
    repository: ProductRepository,
    tmp_path: Path,
) -> None:
    _visit_id, _asset_id, path = _create_imported_visit(
        repository, label="folder-active", folder=True, tmp_path=tmp_path
    )

    preview = repository.preview_storage_cleanup()

    assert preview.eligible_media_count == 0
    protected = {item.category for item in preview.protected_counts}
    assert "legacy_representative_evidence" in protected
    assert path.exists()


def test_reviewed_imported_visit_media_stays_protected_indefinitely(
    repository: ProductRepository,
) -> None:
    """Reviewed truth protects the evidence needed to render it: an
    imported Visit's media stays protected forever once reviewed, exactly
    like a linked primary frame, as long as the Visit itself is not
    superseded -- being old and reviewed is never enough by itself."""
    visit_id, asset_id, path = _create_imported_visit(repository, label="manual-reviewed")
    with repository.session_factory() as session:
        with session.begin():
            asset = session.get(MediaAssetModel, asset_id)
            assert asset is not None
            asset.created_at = datetime.now(UTC) - timedelta(days=3650)
            visit = session.get(VisitModel, visit_id)
            assert visit is not None
            visit.review_status = "reviewed"
            visit.reviewed_label = "northern_cardinal"
    repository.update_storage_retention_settings(
        _settings_payload(
            "manual-reviewed-settings",
            reviewed_non_bird_age_days=30,
            retain_reviewed_bird_wildlife_evidence=False,
        )
    )

    preview = repository.preview_storage_cleanup()

    assert preview.eligible_media_count == 0
    protected = {item.category for item in preview.protected_counts}
    assert "legacy_representative_evidence" in protected
    assert path.exists()


def test_corrected_imported_visit_media_stays_protected(
    repository: ProductRepository,
) -> None:
    """A correction (an already-reviewed Visit's label changed) never marks
    the Visit superseded -- corrected truth is exactly as protected as
    first-time-reviewed truth."""
    visit_id, asset_id, path = _create_imported_visit(repository, label="manual-corrected")
    with repository.session_factory() as session:
        with session.begin():
            asset = session.get(MediaAssetModel, asset_id)
            assert asset is not None
            asset.created_at = datetime.now(UTC) - timedelta(days=3650)
            visit = session.get(VisitModel, visit_id)
            assert visit is not None
            visit.review_status = "reviewed"
            visit.reviewed_label = "blue_jay"
            session.flush()
            # A correction: the label changes, review truth is re-affirmed,
            # is_superseded is never touched by a correction.
            visit.reviewed_label = "northern_cardinal"
            assert visit.is_superseded is False

    preview = repository.preview_storage_cleanup()

    assert preview.eligible_media_count == 0
    with repository.session_factory() as session:
        visit = session.get(VisitModel, visit_id)
        assert visit is not None
        assert visit.reviewed_label == "northern_cardinal"
        assert visit.is_superseded is False
    assert path.exists()


def test_superseded_imported_media_protected_before_age_threshold(
    repository: ProductRepository,
) -> None:
    visit_id, asset_id, path = _create_imported_visit(repository, label="manual-too-recent")
    with repository.session_factory() as session:
        with session.begin():
            asset = session.get(MediaAssetModel, asset_id)
            assert asset is not None
            asset.created_at = datetime.now(UTC) - timedelta(days=1)
            visit = session.get(VisitModel, visit_id)
            assert visit is not None
            visit.is_superseded = True
    repository.update_storage_retention_settings(
        _settings_payload("manual-too-recent-settings", superseded_evidence_age_days=90)
    )

    preview = repository.preview_storage_cleanup()

    assert preview.eligible_media_count == 0
    protected = {item.category for item in preview.protected_counts}
    assert "superseded_evidence_too_recent" in protected
    assert path.exists()


def test_superseded_imported_media_becomes_eligible_and_purges_with_no_dangling_reference(
    repository: ProductRepository,
) -> None:
    """The reproducer for Defect 1: once every Visit referencing an
    imported asset is superseded and old enough, ordinary retention -- the
    documented contract -- makes it eligible, exactly like any other
    Visit-linked evidence. After a real purge: the file is gone, the
    MediaAssetModel row survives forever as an audit trail (the same,
    already-accepted convention every other purged category already uses),
    the Visit/Event rows and their truth fields are completely untouched,
    and reading the now-orphaned representative_media_path does not crash."""
    visit_id, asset_id, path = _create_imported_visit(repository, label="manual-supersede")
    with repository.session_factory() as session:
        with session.begin():
            asset = session.get(MediaAssetModel, asset_id)
            assert asset is not None
            asset.created_at = datetime.now(UTC) - timedelta(days=365)
            visit = session.get(VisitModel, visit_id)
            assert visit is not None
            visit.is_superseded = True
    repository.update_storage_retention_settings(
        _settings_payload("manual-supersede-settings", superseded_evidence_age_days=30)
    )

    preview = repository.preview_storage_cleanup()
    assert preview.eligible_media_count == 1
    assert {c.category for c in preview.categories} == {"superseded_only_evidence"}

    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="manual-supersede-cleanup",
        )
    )
    assert result.state == "quarantined"
    assert not path.exists()

    with repository.session_factory() as session:
        with session.begin():
            batch = session.get(StorageCleanupBatchModel, result.batch_id)
            assert batch is not None
            batch.recovery_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    purged = repository.purge_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="manual-supersede-purge"),
    )
    assert purged is not None and purged.state == "purged"

    with repository.session_factory() as session:
        # DB -> media coherence: the MediaAssetModel row is retained forever
        # as an audit trail (mirrors every other purge category); reading it
        # -- and the Visit that used to point at it -- never crashes.
        asset = session.get(MediaAssetModel, asset_id)
        assert asset is not None
        visit = session.get(VisitModel, visit_id)
        assert visit is not None
        assert visit.is_superseded is True
        assert visit.representative_media_path == str(path)
        assert visit.reviewed_label is None
        event = session.get(EventModel, visit.event_id)
        assert event is not None
        assert event.event_type == "manual_media_import"
    assert not path.exists()


def test_legacy_representative_media_shared_by_two_visits_protected_until_all_superseded(
    repository: ProductRepository,
) -> None:
    """Defensive: if more than one Visit's representative_media_path ever
    points at the same imported asset, it stays protected as long as ANY
    referencing Visit is active -- never eligible just because one of
    several referencing Visits was superseded."""
    visit_id, asset_id, path = _create_imported_visit(repository, label="shared-a")
    other_visit_id, _other_asset_id, _other_path = _create_imported_visit(
        repository, label="shared-b"
    )
    with repository.session_factory() as session:
        with session.begin():
            asset = session.get(MediaAssetModel, asset_id)
            assert asset is not None
            asset.created_at = datetime.now(UTC) - timedelta(days=365)
            other_visit = session.get(VisitModel, other_visit_id)
            assert other_visit is not None
            other_visit.representative_media_path = asset.local_path
            visit = session.get(VisitModel, visit_id)
            assert visit is not None
            visit.is_superseded = True
    repository.update_storage_retention_settings(
        _settings_payload("shared-legacy-settings", superseded_evidence_age_days=30)
    )

    preview = repository.preview_storage_cleanup()
    assert preview.eligible_media_count == 0
    protected = {item.category for item in preview.protected_counts}
    assert "legacy_representative_evidence" in protected
    assert path.exists()

    with repository.session_factory() as session:
        with session.begin():
            other_visit = session.get(VisitModel, other_visit_id)
            assert other_visit is not None
            other_visit.is_superseded = True

    preview_after = repository.preview_storage_cleanup()
    assert preview_after.eligible_media_count == 1
    assert {c.category for c in preview_after.categories} == {"superseded_only_evidence"}


# Defect 2: a `"staging"` (interrupted) cleanup batch could only ever be
# restored, never purged -- `purge_storage_cleanup_batch`'s own purge query
# only ever considers items already durably `quarantined`, which an
# interrupted item never reaches on its own. The fix teaches purge to first
# resolve a `staging` batch (reusing the exact reconciliation
# `execute_storage_cleanup` already performs at the end of a clean run) to a
# real `quarantined`/`failed` terminal state before proceeding.


def test_staging_batch_purge_completes_interrupted_move_and_removes_file(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_path = _add_media(repository, media_id="retention-staging-purge", age_days=365)
    preview = repository.preview_storage_cleanup()
    real_move = repository._move_storage_item_to_recovery

    def move_then_interrupt(item: StorageCleanupItemModel) -> bool:
        assert real_move(item)
        raise OSError("simulated interruption after recovery move")

    monkeypatch.setattr(repository, "_move_storage_item_to_recovery", move_then_interrupt)
    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-staging-purge",
        )
    )
    assert result.state == "staging"
    assert not original_path.exists()
    with repository.session_factory() as session:
        item = session.scalar(
            select(StorageCleanupItemModel).where(
                StorageCleanupItemModel.batch_id == result.batch_id
            )
        )
        assert item is not None and item.state == "staged"

    with pytest.raises(ValueError, match="storage_cleanup_recovery_active"):
        repository.purge_storage_cleanup_batch(
            result.batch_id,
            StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-staging-purge-early"),
        )
    with repository.session_factory() as session:
        with session.begin():
            batch = session.get(StorageCleanupBatchModel, result.batch_id)
            assert batch is not None
            batch.recovery_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    purged = repository.purge_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-staging-purge-final"),
    )

    assert purged is not None and purged.state == "purged"
    with repository.session_factory() as session:
        item = session.scalar(
            select(StorageCleanupItemModel).where(
                StorageCleanupItemModel.batch_id == result.batch_id
            )
        )
        assert item is not None and item.state == "purged"
        batch = session.get(StorageCleanupBatchModel, result.batch_id)
        assert batch is not None and batch.state == "purged"
    recovery_path = repository.media_root / ".recovery" / result.batch_id / "retention-staging-purge.bin"
    assert not recovery_path.exists()
    assert not original_path.exists()


def test_staging_batch_purge_is_idempotent_on_repeat(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _add_media(repository, media_id="retention-staging-idempotent", age_days=365)
    preview = repository.preview_storage_cleanup()
    real_move = repository._move_storage_item_to_recovery

    def move_then_interrupt(item: StorageCleanupItemModel) -> bool:
        assert real_move(item)
        raise OSError("simulated interruption after recovery move")

    monkeypatch.setattr(repository, "_move_storage_item_to_recovery", move_then_interrupt)
    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-staging-idempotent",
        )
    )
    assert result.state == "staging"
    with repository.session_factory() as session:
        with session.begin():
            batch = session.get(StorageCleanupBatchModel, result.batch_id)
            assert batch is not None
            batch.recovery_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    first = repository.purge_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-staging-idempotent-purge"),
    )
    assert first is not None and first.state == "purged" and first.idempotent is False

    second = repository.purge_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-staging-idempotent-purge"),
    )
    assert second is not None and second.idempotent is True
    assert second.state == "purged"

    third = repository.purge_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="a-different-later-key"),
    )
    assert third is not None and third.state == "purged"


def test_staging_batch_with_all_items_restored_during_reconciliation_resolves_to_failed(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If reconciliation finds the live product state changed since the
    interrupted move (its link snapshot no longer matches) and successfully
    restores the file back, there is nothing left to purge. The batch must
    resolve to the real, explicit `failed` outcome -- never a misleading
    `purged` with zero items actually removed."""
    _add_media(repository, media_id="retention-staging-restored-away", age_days=365)
    preview = repository.preview_storage_cleanup()
    real_move = repository._move_storage_item_to_recovery

    def move_then_interrupt(item: StorageCleanupItemModel) -> bool:
        assert real_move(item)
        raise OSError("simulated interruption after recovery move")

    monkeypatch.setattr(repository, "_move_storage_item_to_recovery", move_then_interrupt)
    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-staging-restored-away",
        )
    )
    assert result.state == "staging"

    phantom_link = {
        "id": "phantom-link",
        "visit_id": "phantom-visit",
        "captured_at": datetime.now(UTC).isoformat(),
        "frame_sequence": None,
        "sort_order": 0,
        "is_primary": True,
        "evidence_role": "monitoring_frame",
        "created_at": datetime.now(UTC).isoformat(),
    }
    with repository.session_factory() as session:
        with session.begin():
            item = session.scalar(
                select(StorageCleanupItemModel).where(
                    StorageCleanupItemModel.batch_id == result.batch_id
                )
            )
            assert item is not None
            item.evidence_links_json = json.dumps([phantom_link])

    purged = repository.purge_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-staging-restored-away-purge"),
    )

    assert purged is not None
    assert purged.state == "failed"
    assert purged.moved_to_recovery_count == 0
    with repository.session_factory() as session:
        item = session.scalar(
            select(StorageCleanupItemModel).where(
                StorageCleanupItemModel.batch_id == result.batch_id
            )
        )
        assert item is not None and item.state == "failed"
    original_path = repository.media_root / "retention-staging-restored-away.bin"
    assert original_path.exists()  # genuinely restored back -- nothing lost

    repeated = repository.purge_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-staging-restored-away-purge"),
    )
    assert repeated is not None and repeated.idempotent is True


def test_staging_batch_still_ambiguous_after_reconciliation_rejects_purge(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid transition rejected: if reconciliation cannot even restore
    the file back (product context changed AND the original location is
    unavailable), the item stays genuinely ambiguous. Purge must refuse
    with the standard unavailable error rather than report a false terminal
    outcome -- restore remains the escape hatch."""
    _add_media(repository, media_id="retention-staging-ambiguous", age_days=365)
    preview = repository.preview_storage_cleanup()
    real_move = repository._move_storage_item_to_recovery

    def move_then_interrupt(item: StorageCleanupItemModel) -> bool:
        assert real_move(item)
        raise OSError("simulated interruption after recovery move")

    monkeypatch.setattr(repository, "_move_storage_item_to_recovery", move_then_interrupt)
    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-staging-ambiguous",
        )
    )
    assert result.state == "staging"

    monkeypatch.setattr(repository, "_restore_storage_item_from_recovery", lambda item: False)
    phantom_link = {
        "id": "phantom-link",
        "visit_id": "phantom-visit",
        "captured_at": datetime.now(UTC).isoformat(),
        "frame_sequence": None,
        "sort_order": 0,
        "is_primary": True,
        "evidence_role": "monitoring_frame",
        "created_at": datetime.now(UTC).isoformat(),
    }
    with repository.session_factory() as session:
        with session.begin():
            item = session.scalar(
                select(StorageCleanupItemModel).where(
                    StorageCleanupItemModel.batch_id == result.batch_id
                )
            )
            assert item is not None
            item.evidence_links_json = json.dumps([phantom_link])

    with pytest.raises(ValueError, match="storage_cleanup_purge_unavailable"):
        repository.purge_storage_cleanup_batch(
            result.batch_id,
            StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-staging-ambiguous-purge"),
        )

    with repository.session_factory() as session:
        batch = session.get(StorageCleanupBatchModel, result.batch_id)
        assert batch is not None and batch.state == "staging"
        item = session.scalar(
            select(StorageCleanupItemModel).where(
                StorageCleanupItemModel.batch_id == result.batch_id
            )
        )
        assert item is not None and item.state == "moving"


def test_staging_batch_purge_survives_deletion_permission_failure(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real deletion failure (e.g. a permission error) during the purge
    step following staging-batch reconciliation must not corrupt state: the
    item stays quarantined (still restorable), the batch reports
    `restore_conflict`, never a false `purged`, and the call remains safely
    retryable."""
    _add_media(repository, media_id="retention-staging-permission", age_days=365)
    preview = repository.preview_storage_cleanup()
    real_move = repository._move_storage_item_to_recovery

    def move_then_interrupt(item: StorageCleanupItemModel) -> bool:
        assert real_move(item)
        raise OSError("simulated interruption after recovery move")

    monkeypatch.setattr(repository, "_move_storage_item_to_recovery", move_then_interrupt)
    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="retention-staging-permission",
        )
    )
    assert result.state == "staging"
    with repository.session_factory() as session:
        with session.begin():
            batch = session.get(StorageCleanupBatchModel, result.batch_id)
            assert batch is not None
            batch.recovery_expires_at = datetime.now(UTC) - timedelta(seconds=1)

    monkeypatch.setattr(repository, "_purge_storage_item", lambda item: False)

    purged = repository.purge_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-staging-permission-purge"),
    )

    assert purged is not None
    assert purged.state == "restore_conflict"
    assert purged.moved_to_recovery_count == 0
    with repository.session_factory() as session:
        item = session.scalar(
            select(StorageCleanupItemModel).where(
                StorageCleanupItemModel.batch_id == result.batch_id
            )
        )
        assert item is not None and item.state == "quarantined"

    repeated = repository.purge_storage_cleanup_batch(
        result.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="retention-staging-permission-purge"),
    )
    assert repeated is not None and repeated.idempotent is True


# Defect 3: MAX_STORAGE_CLEANUP_HISTORY_ITEMS bounded only a read-page size
# and an unrelated automatic-purge chunk size -- the underlying
# storage_cleanup_batches table had no row-deletion path anywhere and grew
# forever. The fix prunes the oldest fully-resolved (purged/restored/failed)
# rows beyond the newest MAX_STORAGE_CLEANUP_HISTORY_ITEMS at the end of
# every write path that can produce a newly-eligible one.


def _seed_resolved_history_batches(
    repository: ProductRepository,
    *,
    count: int,
    prefix: str,
    state: str = "purged",
) -> None:
    now = datetime.now(UTC)
    with repository.session_factory() as session:
        with session.begin():
            for index in range(count):
                batch_id = f"{prefix}-{index:03d}"
                session.add(
                    StorageCleanupBatchModel(
                        id=batch_id,
                        origin="automatic",
                        state=state,
                        preview_token=f"preview-{batch_id}",
                        state_fingerprint=f"fingerprint-{batch_id}",
                        policy_revision=1,
                        idempotency_key=f"exec-{batch_id}",
                        created_at=now - timedelta(days=count - index),
                        executed_at=now - timedelta(days=count - index),
                        recovery_expires_at=now - timedelta(days=1),
                        restored_at=now - timedelta(days=1) if state == "restored" else None,
                        purged_at=now - timedelta(days=1) if state == "purged" else None,
                        summary_json=json.dumps({"permanently_purged_count": 1}),
                        safe_error=None,
                        last_purge_idempotency_key=f"purge-{batch_id}" if state == "purged" else None,
                        last_restore_idempotency_key=f"restore-{batch_id}" if state == "restored" else None,
                    )
                )


def test_cleanup_history_table_row_count_exceeds_bound_before_any_pruning_runs(
    repository: ProductRepository,
) -> None:
    """Proves the raw defect directly: seeding more resolved batches than
    the intended bound, with no write path invoked afterward, leaves the
    underlying table over the bound -- the bound is only ever enforced as a
    side effect of a write path, never retroactively."""
    total = MAX_STORAGE_CLEANUP_HISTORY_ITEMS + 5
    _seed_resolved_history_batches(repository, count=total, prefix="history-raw-seed")

    with repository.session_factory() as session:
        row_count = session.scalar(select(func.count(StorageCleanupBatchModel.id)))
    assert row_count == total


def test_cleanup_history_is_bounded_after_a_real_execute_pass(
    repository: ProductRepository,
) -> None:
    total = MAX_STORAGE_CLEANUP_HISTORY_ITEMS + 5
    _seed_resolved_history_batches(repository, count=total, prefix="history-seed")

    # Any ordinary write path that can complete a batch prunes history as a
    # side effect -- a real orphaned-media cleanup pass here, matching how a
    # real deployment's own daily/weekly automatic pass is the intended
    # enforcement point, not a dedicated sweep job.
    _add_media(repository, media_id="history-trigger", age_days=45)
    preview = repository.preview_storage_cleanup()
    triggering = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="history-trigger-exec",
        )
    )
    assert triggering.state == "quarantined"

    with repository.session_factory() as session:
        row_count = session.scalar(select(func.count(StorageCleanupBatchModel.id)))
        remaining_ids = set(session.scalars(select(StorageCleanupBatchModel.id)).all())
    # The newest MAX_STORAGE_CLEANUP_HISTORY_ITEMS seeded (purged, prunable)
    # batches survive, plus the just-created (quarantined, not yet
    # prunable) triggering batch -- never fewer, never materially more.
    assert row_count == MAX_STORAGE_CLEANUP_HISTORY_ITEMS + 1
    assert "history-seed-000" not in remaining_ids  # oldest pruned first
    assert "history-seed-004" not in remaining_ids
    assert f"history-seed-{total - 1:03d}" in remaining_ids  # newest seed survives
    assert triggering.batch_id in remaining_ids  # the batch just created survives


def test_cleanup_history_pruning_never_removes_a_batch_with_live_recovery_files(
    repository: ProductRepository,
) -> None:
    """A `quarantined`/`staging`/`restore_conflict` batch still holds real
    files under `.recovery/<batch_id>/`; pruning must never delete its row
    merely for being old, or those files become permanently unrestorable
    and unpurgeable -- a real orphan this fix must not create."""
    now = datetime.now(UTC)
    old_but_live_id = "history-old-but-quarantined"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                StorageCleanupBatchModel(
                    id=old_but_live_id,
                    origin="manual",
                    state="quarantined",
                    preview_token="preview-old-live",
                    state_fingerprint="fingerprint-old-live",
                    policy_revision=1,
                    idempotency_key="exec-old-live",
                    created_at=now - timedelta(days=400),
                    executed_at=now - timedelta(days=400),
                    recovery_expires_at=now - timedelta(days=386),
                    restored_at=None,
                    purged_at=None,
                    summary_json=json.dumps({"media_count": 1}),
                    safe_error=None,
                )
            )
    _seed_resolved_history_batches(
        repository, count=MAX_STORAGE_CLEANUP_HISTORY_ITEMS + 5, prefix="history-newer-resolved"
    )

    with repository.session_factory() as session:
        with session.begin():
            repository._prune_storage_cleanup_history(session)

    with repository.session_factory() as session:
        remaining_ids = set(session.scalars(select(StorageCleanupBatchModel.id)).all())
    assert old_but_live_id in remaining_ids


def test_history_prune_failure_leaves_batch_safely_recoverable_not_corrupted(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pruning runs inside the same final transaction as the batch's own
    terminal-state write. If it ever raised there, that transaction rolls
    back -- the batch is left exactly where any other interruption at that
    same point already leaves it (`staging`, its file already moved, links
    already removed, fully recoverable), never a new, worse, corrupted
    state."""
    original_path = _add_media(repository, media_id="retention-prune-boundary", age_days=45)
    preview = repository.preview_storage_cleanup()

    def failing_prune(self: ProductRepository, session: object, *, keep: int = 0) -> None:
        raise RuntimeError("simulated failure exactly at the transaction boundary")

    monkeypatch.setattr(ProductRepository, "_prune_storage_cleanup_history", failing_prune)

    with pytest.raises(RuntimeError, match="simulated failure"):
        repository.execute_storage_cleanup(
            StorageCleanupExecuteRequest(
                preview_token=preview.preview_token,
                confirm=True,
                idempotency_key="retention-prune-boundary",
            )
        )

    # The item's own move already committed independently (an earlier, real
    # transaction) -- the file really is gone from its original location --
    # but the batch's own terminal-state write, sharing a transaction with
    # the now-failing prune, rolled back to its pre-reconciliation state.
    assert not original_path.exists()
    with repository.session_factory() as session:
        batch = session.scalar(
            select(StorageCleanupBatchModel).where(
                StorageCleanupBatchModel.idempotency_key == "retention-prune-boundary"
            )
        )
        assert batch is not None
        assert batch.state == "staging"
        batch_id = batch.id

    monkeypatch.undo()
    restored = repository.restore_storage_cleanup_batch(
        batch_id,
        StorageCleanupRestoreRequest(idempotency_key="retention-prune-boundary-restore"),
    )
    assert restored is not None and restored.state == "restored"
    assert original_path.exists()


# Integrated acceptance: one product-shaped pass proving all three fixes
# interact correctly with ordinary retention execution in a single run.


def test_integrated_cleanup_pass_resolves_all_three_defects_correctly(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Enough pre-existing resolved history to already exceed the bound.
    _seed_resolved_history_batches(
        repository, count=MAX_STORAGE_CLEANUP_HISTORY_ITEMS + 2, prefix="integrated-history"
    )

    # Ineligible: a Reviewed, camera-captured Visit's primary evidence.
    reviewed_path = _add_media(repository, media_id="integrated-reviewed-primary", age_days=3650)
    _add_active_visit_with_evidence(
        repository,
        visit_id="integrated-reviewed-visit",
        evidence=[("integrated-reviewed-primary", True)],
        review_status="reviewed",
        reviewed_label="northern_cardinal",
    )

    # A staging (interrupted) batch, from an unrelated ordinary orphaned
    # asset, that must resolve to a valid terminal state via purge. Run
    # this before the imported media below becomes independently eligible,
    # so this batch's own interrupted candidate set is exactly the orphan.
    staging_path = _add_media(repository, media_id="integrated-staging-orphan", age_days=45)
    staging_preview = repository.preview_storage_cleanup()
    assert staging_preview.eligible_media_count == 1
    real_move = repository._move_storage_item_to_recovery

    def move_then_interrupt(item: StorageCleanupItemModel) -> bool:
        assert real_move(item)
        raise OSError("simulated interruption after recovery move")

    monkeypatch.setattr(repository, "_move_storage_item_to_recovery", move_then_interrupt)
    staging_result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=staging_preview.preview_token,
            confirm=True,
            idempotency_key="integrated-staging-exec",
        )
    )
    assert staging_result.state == "staging"
    assert not staging_path.exists()
    monkeypatch.setattr(repository, "_move_storage_item_to_recovery", real_move)

    # Eligible: superseded, old-enough imported media (Defect 1).
    import_visit_id, import_asset_id, imported_path = _create_imported_visit(
        repository, label="integrated-imported"
    )
    with repository.session_factory() as session:
        with session.begin():
            asset = session.get(MediaAssetModel, import_asset_id)
            assert asset is not None
            asset.created_at = datetime.now(UTC) - timedelta(days=365)
            visit = session.get(VisitModel, import_visit_id)
            assert visit is not None
            visit.is_superseded = True
    repository.update_storage_retention_settings(
        _settings_payload("integrated-settings", superseded_evidence_age_days=30)
    )

    # Now run the real, product-shaped cleanup pass over the imported,
    # superseded evidence -- exercising Defect 1's fix and, as a side
    # effect, Defect 3's history-bound enforcement together.
    preview = repository.preview_storage_cleanup()
    assert preview.eligible_media_count == 1
    assert {c.category for c in preview.categories} == {"superseded_only_evidence"}
    result = repository.execute_storage_cleanup(
        StorageCleanupExecuteRequest(
            preview_token=preview.preview_token,
            confirm=True,
            idempotency_key="integrated-cleanup-exec",
        )
    )
    assert result.state == "quarantined"
    assert not imported_path.exists()

    # Resolve the interrupted staging batch -- exercises Defect 2's fix.
    with repository.session_factory() as session:
        with session.begin():
            batch = session.get(StorageCleanupBatchModel, staging_result.batch_id)
            assert batch is not None
            batch.recovery_expires_at = datetime.now(UTC) - timedelta(seconds=1)
    staging_purged = repository.purge_storage_cleanup_batch(
        staging_result.batch_id,
        StorageCleanupPurgeRequest(confirm=True, idempotency_key="integrated-staging-purge"),
    )
    assert staging_purged is not None and staging_purged.state == "purged"

    # -- Final assertions: correct files retained, correct files removed --
    assert reviewed_path.exists()  # Reviewed truth's evidence: retained
    assert not imported_path.exists()  # superseded imported media: removed
    recovery_path = (
        repository.media_root / ".recovery" / staging_result.batch_id / "integrated-staging-orphan.bin"
    )
    assert not recovery_path.exists()  # staging batch: actually purged

    # -- cleanup batch in a valid terminal state --
    with repository.session_factory() as session:
        staging_batch = session.get(StorageCleanupBatchModel, staging_result.batch_id)
        assert staging_batch is not None and staging_batch.state == "purged"
        cleanup_batch = session.get(StorageCleanupBatchModel, result.batch_id)
        assert cleanup_batch is not None and cleanup_batch.state == "quarantined"

    # -- history within bound --
    with repository.session_factory() as session:
        row_count = session.scalar(select(func.count(StorageCleanupBatchModel.id)))
    assert row_count is not None and row_count <= MAX_STORAGE_CLEANUP_HISTORY_ITEMS + 3

    # -- DB/media coherence intact --
    with repository.session_factory() as session:
        reviewed_visit = session.get(VisitModel, "integrated-reviewed-visit")
        assert reviewed_visit is not None
        assert reviewed_visit.reviewed_label == "northern_cardinal"
        imported_visit = session.get(VisitModel, import_visit_id)
        assert imported_visit is not None
        assert imported_visit.is_superseded is True
        imported_asset = session.get(MediaAssetModel, import_asset_id)
        assert imported_asset is not None  # retained forever as an audit trail
