from datetime import UTC, datetime, timedelta
from pathlib import Path
from zipfile import ZipFile

import pytest
from sqlalchemy import func, select

from mockingbird.api.schemas import (
    LabelCategory,
    StorageCleanupExecuteRequest,
    StorageCleanupPurgeRequest,
    StorageCleanupRestoreRequest,
    StorageRetentionFrequency,
    StorageRetentionSettingsUpdate,
)
from mockingbird.observation.contracts import CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE
from mockingbird.repository.product_repository import MotionEvidenceModel, ProductRepository
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
        ("test-wildlife-unknown", LabelCategory.unknown.value, False),
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
            assert result is is_wildlife_category(category)

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
