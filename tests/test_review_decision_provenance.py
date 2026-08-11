"""Review Decision Provenance / Truth Boundary v1 (see
docs/review-decision-provenance-contract.md).

Covers the milestone's own Part 12 test list: human review is authority-
eligible; agent/model diagnostic assessment is never authority-eligible and
is never silently treated as human; omitted provenance never defaults to
human; reviewed-only export and training eligibility exclude non-
authoritative rows; Bird Log/history never misrepresents a diagnostic
assessment as user-confirmed; legacy/unattributed handling is explicit and
deterministic; imported curated truth (demo seed content) follows its
declared eligibility; persistence round-trips preserve provenance; and the
bounded provenance-repair path (Part 8) correctly reclassifies one row
without touching unrelated review truth.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect

from mockingbird.api.schemas import (
    DatasetExportCreate,
    ReviewCorrectionCreate,
    VisitReviewReopenCreate,
    VisitReviewRevisionCreate,
    WildlifeJournalOverviewRequest,
)
from mockingbird.repository.product_repository import (
    ProductRepository,
    ReviewProvenanceConflictError,
    ReviewRevisionConflictError,
)
from mockingbird.review_provenance import ReviewProvenanceError, discloses_non_human_review
from mockingbird.storage.database import CURRENT_DATABASE_SCHEMA_VERSION, create_database_engine

STREAM_ID = "stream-backyard-feeder"
BIRD_VISIT_ID = "visit-bird-feeder-001"
AGENT_IDENTITY = "claude-agent-visual-inspection-2026-08-10"


def repository_for(path: Path) -> ProductRepository:
    return ProductRepository(db_url=f"sqlite:///{path}")


# --- 1/2/3/4: origin -> authority eligibility at creation time -------------


def test_human_review_establishes_authoritative_truth(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")

    result = repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=BIRD_VISIT_ID,
            label="northern_cardinal",
            review_origin="human",
        )
    )

    assert result.review_label.review_origin == "human"
    assert result.review_label.is_authoritative is True
    visit = repository.get_visit(BIRD_VISIT_ID)
    assert visit.review_status.value == "reviewed"
    assert visit.reviewed_label == "northern_cardinal"
    assert repository.visit_is_dataset_ready(visit) is True


def test_agent_diagnostic_assessment_never_establishes_truth(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")

    result = repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=BIRD_VISIT_ID,
            label="false_positive",
            notes="[AGENT VISUAL REVIEW -- box lands on bare bark, no bird -- not independently human-confirmed]",
            review_origin="agent_diagnostic",
            reviewer_identity=AGENT_IDENTITY,
        )
    )

    # The assessment is durably recorded -- never silently dropped.
    assert result.review_label.label == "false_positive"
    assert result.review_label.review_origin == "agent_diagnostic"
    # ... but it never becomes authoritative, and the API response says so
    # explicitly rather than requiring the caller to infer it.
    assert result.review_label.is_authoritative is False

    # And critically, it never mutated the Visit/Event it targeted: an
    # agent's own diagnostic conclusion must never be silently treated as
    # equivalent to a human Review Decision.
    visit = repository.get_visit(BIRD_VISIT_ID)
    assert visit.review_status.value == "needs_review"
    assert visit.reviewed_label is None
    assert repository.visit_is_dataset_ready(visit) is False

    # The row is still visible through the Visit's full correction history
    # (`review_labels_for_visit` itself is an *effective-current-truth*
    # view -- pre-existing behavior, now also authority-aware -- so a
    # non-authoritative row is correctly absent from it; the full history
    # is where "do not delete or pretend they never happened" applies).
    history = repository.visit_review_history(BIRD_VISIT_ID)
    assert history is not None
    assert any(entry.label == "false_positive" and not entry.is_authoritative for entry in history.entries)


def test_omitted_review_origin_does_not_default_to_human(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")

    # No review_origin at all -- simulates a caller (automation, a future
    # LLM integration, a careless script) that never sends the field.
    result = repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=BIRD_VISIT_ID, label="northern_cardinal")
    )

    assert result.review_label.review_origin is None
    assert result.review_label.is_authoritative is False
    visit = repository.get_visit(BIRD_VISIT_ID)
    assert visit.review_status.value == "needs_review"
    assert visit.reviewed_label is None


def test_bulk_correction_and_fast_review_also_require_explicit_origin(tmp_path: Path) -> None:
    """The create-family endpoints beyond the plain POST (bulk correction,
    Fast Review) share the identical writer, so the same "never default to
    human" rule must hold for them too."""

    from mockingbird.api.schemas import ReviewQueueBulkCorrectionRequest, ReviewQueueBulkCorrectionTargetType

    repository = repository_for(tmp_path / "db.sqlite3")

    response = repository.bulk_correct_review_queue_items(
        ReviewQueueBulkCorrectionRequest(
            target_ids=[BIRD_VISIT_ID],
            target_type=ReviewQueueBulkCorrectionTargetType.visit,
            label="northern_cardinal",
            # review_origin omitted entirely
        )
    )
    assert response.succeeded_count == 1
    visit = repository.get_visit(BIRD_VISIT_ID)
    assert visit.review_status.value == "needs_review", "an omitted-origin bulk correction must not establish truth"


# --- 5/6: reviewed-only export and training eligibility --------------------


def test_reviewed_only_export_excludes_non_authoritative_review(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=BIRD_VISIT_ID,
            label="northern_cardinal",
            review_origin="agent_diagnostic",
            reviewer_identity=AGENT_IDENTITY,
        )
    )

    export = repository.create_dataset_export(DatasetExportCreate(name="Reviewed-only export", reviewed_only=True))
    manifest = repository.build_dataset_manifest(export.id)

    assert manifest is not None
    assert all(record.visit_id != BIRD_VISIT_ID for record in manifest.records), (
        "a reviewed-only export promises human-reviewed truth; an agent diagnostic assessment must not satisfy it"
    )


def test_reviewed_only_export_includes_human_review(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=BIRD_VISIT_ID, label="northern_cardinal", review_origin="human"
        )
    )

    export = repository.create_dataset_export(DatasetExportCreate(name="Reviewed-only export", reviewed_only=True))
    manifest = repository.build_dataset_manifest(export.id)

    assert manifest is not None
    assert any(
        record.visit_id == BIRD_VISIT_ID and record.label == "northern_cardinal" and record.dataset_ready
        for record in manifest.records
    )


def test_training_eligibility_excludes_agent_diagnostic_assessment(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=BIRD_VISIT_ID,
            label="northern_cardinal",
            review_origin="agent_diagnostic",
            reviewer_identity=AGENT_IDENTITY,
        )
    )

    manifest = repository.build_classifier_training_manifest()

    assert all(example.visit_id != BIRD_VISIT_ID for example in manifest.examples)
    skipped = {record.visit_id: record.reason for record in manifest.skipped_records}
    assert skipped.get(BIRD_VISIT_ID) in {"unreviewed", "missing_review_label"}


# --- 8: Bird Log / history never misrepresents a diagnostic assessment -----


def test_bird_log_journal_excludes_agent_diagnostic_assessment(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=BIRD_VISIT_ID,
            label="northern_cardinal",
            review_origin="agent_diagnostic",
            reviewer_identity=AGENT_IDENTITY,
        )
    )

    overview = repository.wildlife_journal_overview(WildlifeJournalOverviewRequest())
    assert all(row.label != "northern_cardinal" for row in overview.labels), (
        "Bird Log must never present an agent diagnostic assessment as confirmed wildlife"
    )


def test_bird_log_journal_includes_human_review(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=BIRD_VISIT_ID, label="northern_cardinal", review_origin="human"
        )
    )

    overview = repository.wildlife_journal_overview(WildlifeJournalOverviewRequest())
    assert any(row.label == "northern_cardinal" for row in overview.labels)


def test_visit_review_history_marks_diagnostic_entry_as_not_current_and_not_authoritative(
    tmp_path: Path,
) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=BIRD_VISIT_ID,
            label="false_positive",
            review_origin="agent_diagnostic",
            reviewer_identity=AGENT_IDENTITY,
        )
    )

    history = repository.visit_review_history(BIRD_VISIT_ID)
    assert history is not None
    assert history.review_status.value == "needs_review"
    assert len(history.entries) == 1
    entry = history.entries[0]
    assert entry.is_authoritative is False
    assert entry.review_origin == "agent_diagnostic"
    # `is_current` means "this is the Visit's current effective reviewed
    # truth" -- a diagnostic entry must never claim that, even though it is
    # the only/most recent row.
    assert entry.is_current is False


def test_revise_and_reopen_reject_non_authoritative_origin(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")
    detail_result = repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=BIRD_VISIT_ID, label="northern_cardinal", review_origin="human"
        )
    )
    # The public, documented way to get a state token: the History response
    # already carries it.
    history = repository.visit_review_history(BIRD_VISIT_ID)
    assert history is not None

    with pytest.raises(ReviewRevisionConflictError):
        repository.revise_visit_review(
            BIRD_VISIT_ID,
            VisitReviewRevisionCreate(
                label="blue_jay",
                expected_state_token=history.review_state_token,
                idempotency_key="revise-without-authority",
                review_origin="agent_diagnostic",
                reviewer_identity=AGENT_IDENTITY,
            ),
        )
    with pytest.raises(ReviewRevisionConflictError):
        repository.reopen_visit_review(
            BIRD_VISIT_ID,
            VisitReviewReopenCreate(
                expected_state_token=history.review_state_token,
                idempotency_key="reopen-without-authority",
                review_origin=None,
            ),
        )
    # Neither rejected attempt touched the original authoritative truth.
    visit = repository.get_visit(BIRD_VISIT_ID)
    assert visit.reviewed_label == "northern_cardinal"
    assert detail_result.review_label.is_authoritative is True


# --- 9: legacy/unattributed handling is explicit and deterministic ---------


def test_legacy_row_is_backfilled_to_explicit_sentinel_and_stays_authoritative(tmp_path: Path) -> None:
    """A row written by pre-migration code (schema v31) has no
    `review_origin` column at all. Migrating forward must not fabricate
    `"human"`, must not leave it `NULL` (which now means "new row that
    omitted the field"), and must not silently drop its already-established
    Visit truth."""

    db_path = tmp_path / "legacy.sqlite3"
    repository = repository_for(db_path)
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=BIRD_VISIT_ID, label="carolina_wren", review_origin="human"
        )
    )
    repository.close()

    # Roll the schema back to v31 shape: drop the two new columns by
    # rebuilding the table, mirroring the existing migration-test pattern
    # (see test_persistence.py's schema-two/schema-three tests).
    engine = create_database_engine(f"sqlite:///{db_path}")
    with engine.begin() as connection:
        connection.exec_driver_sql(
            """
            CREATE TABLE review_labels_v31 (
                id VARCHAR PRIMARY KEY, target_type VARCHAR NOT NULL, target_id VARCHAR NOT NULL,
                label VARCHAR NOT NULL, notes TEXT, created_at DATETIME NOT NULL,
                reversal_of_review_label_id VARCHAR, prior_review_status VARCHAR, prior_reviewed_label VARCHAR,
                prior_event_review_status VARCHAR, fast_review_session_id VARCHAR, fast_review_idempotency_key VARCHAR,
                supersedes_review_label_id VARCHAR, review_action VARCHAR, revision_idempotency_key VARCHAR
            )
            """
        )
        connection.exec_driver_sql(
            "INSERT INTO review_labels_v31 (id, target_type, target_id, label, notes, created_at, "
            "reversal_of_review_label_id, prior_review_status, prior_reviewed_label, prior_event_review_status, "
            "fast_review_session_id, fast_review_idempotency_key, supersedes_review_label_id, review_action, "
            "revision_idempotency_key) "
            "SELECT id, target_type, target_id, label, notes, created_at, reversal_of_review_label_id, "
            "prior_review_status, prior_reviewed_label, prior_event_review_status, fast_review_session_id, "
            "fast_review_idempotency_key, supersedes_review_label_id, review_action, revision_idempotency_key "
            "FROM review_labels"
        )
        connection.exec_driver_sql("DROP TABLE review_labels")
        connection.exec_driver_sql("ALTER TABLE review_labels_v31 RENAME TO review_labels")
        connection.exec_driver_sql("UPDATE mockingbird_schema SET version = 31 WHERE singleton_id = 1")
    engine.dispose()

    migrated = repository_for(db_path)
    try:
        assert migrated.schema_status.version == CURRENT_DATABASE_SCHEMA_VERSION
        columns = {c["name"] for c in inspect(migrated.engine).get_columns("review_labels")}
        assert {"review_origin", "reviewer_identity"}.issubset(columns)

        labels = migrated.list_review_labels()
        legacy_label = next(label for label in labels if label.target_id == BIRD_VISIT_ID)
        assert legacy_label.review_origin == "legacy_unattributed"
        assert legacy_label.is_authoritative is True, "avoid breaking existing users' history unnecessarily"

        # The Visit's already-established truth is untouched by the migration.
        visit = migrated.get_visit(BIRD_VISIT_ID)
        assert visit.review_status.value == "reviewed"
        assert visit.reviewed_label == "carolina_wren"
        assert migrated.visit_is_dataset_ready(visit) is True
    finally:
        migrated.close()


def test_legacy_unattributed_cannot_be_claimed_by_a_new_create_request(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")
    with pytest.raises(Exception):  # noqa: B017 -- Pydantic ValidationError for an out-of-Literal value
        repository.create_review_label(
            ReviewCorrectionCreate(
                target_type="visit",
                target_id=BIRD_VISIT_ID,
                label="northern_cardinal",
                review_origin="legacy_unattributed",  # type: ignore[arg-type]
            )
        )


# --- 10: imported curated truth follows its declared eligibility rules -----


def test_demo_seed_content_is_imported_curated_and_authoritative(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")

    labels = repository.list_review_labels()
    seeded = next(label for label in labels if label.id == "review-label-squirrel-001")
    assert seeded.review_origin == "imported_curated"
    assert seeded.reviewer_identity
    assert seeded.is_authoritative is True

    # The demo squirrel is a non-bird Event-only correction (Bird Log's
    # Wildlife Journal is bird-species-specific, unaffected by provenance),
    # so verify authority-eligibility through the species-agnostic
    # dataset-readiness signal instead: an `imported_curated` row must
    # still be able to establish export-eligible truth.
    event = repository.get_event("event-squirrel-ground-001")
    assert event is not None
    assert event.review_status.value == "reviewed"
    assert repository.event_is_dataset_ready(event) is True


# --- 11: persistence round-trip preserves provenance ------------------------


def test_provenance_persists_after_repository_reload(tmp_path: Path) -> None:
    db_path = tmp_path / "db.sqlite3"
    repository = repository_for(db_path)
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=BIRD_VISIT_ID,
            label="false_positive",
            review_origin="agent_diagnostic",
            reviewer_identity=AGENT_IDENTITY,
        )
    )
    repository.close()

    reloaded = repository_for(db_path)
    try:
        history = reloaded.visit_review_history(BIRD_VISIT_ID)
        assert history is not None
        assert len(history.entries) == 1
        entry = history.entries[0]
        assert entry.review_origin == "agent_diagnostic"
        assert entry.is_authoritative is False
        visit = reloaded.get_visit(BIRD_VISIT_ID)
        assert visit.review_status.value == "needs_review"

        # `reviewer_identity` is deliberately not part of the user-facing
        # history entry shape; verify its own persistence at the storage
        # layer directly.
        with reloaded.session_factory() as session:
            from mockingbird.storage.models import ReviewLabelModel

            raw = session.query(ReviewLabelModel).filter_by(target_id=BIRD_VISIT_ID).one()
            assert raw.review_origin == "agent_diagnostic"
            assert raw.reviewer_identity == AGENT_IDENTITY
    finally:
        reloaded.close()


# --- 12: the bounded provenance-repair path (Part 8) ------------------------


def test_reclassify_review_label_provenance_repairs_one_row_without_touching_others(
    tmp_path: Path,
) -> None:
    """Simulates exactly the situation Part 8 describes: a ReviewLabel was
    created through the real product review path before this contract
    existed, with only a free-text disclosure marking it non-human. The
    repair reclassifies its structured provenance and reverts the Visit it
    incorrectly marked reviewed -- while a real, unrelated human correction
    on a different Visit is provably untouched."""

    repository = repository_for(tmp_path / "db.sqlite3")

    # A real, unrelated human correction that must survive the repair
    # byte-for-byte.
    unrelated_visit_id = "visit-squirrel-ground-001"
    unrelated = repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=unrelated_visit_id, label="squirrel", review_origin="human")
    )

    # Simulate the pre-fix gap directly: construct the row exactly as the
    # old, provenance-blind code path would have (no review_origin at all,
    # but the visit *was* flipped to reviewed, because that mutation was
    # unconditional before this contract existed).
    from datetime import UTC, datetime

    from mockingbird.storage.models import ReviewLabelModel, VisitModel

    disclosed_notes = (
        "[AGENT VISUAL REVIEW -- 2026-08-10 fresh-cohort field session, not independently "
        "human-confirmed] Box lands on empty grass beside a real bird; classified ambiguous."
    )
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                ReviewLabelModel(
                    id="review-label-pre-fix-001",
                    target_type="visit",
                    target_id=BIRD_VISIT_ID,
                    label="ambiguous",
                    notes=disclosed_notes,
                    created_at=datetime.now(UTC),
                )
            )
            visit_model = session.get(VisitModel, BIRD_VISIT_ID)
            visit_model.reviewed_label = "ambiguous"
            visit_model.review_status = "reviewed"

    # Sanity: before the repair, this really does misrepresent the Visit as
    # reviewed, exactly like the real 2026-08-10 rows did.
    before = repository.get_visit(BIRD_VISIT_ID)
    assert before.review_status.value == "reviewed"

    # The maintenance discovery step: scan for the disclosure marker (the
    # same logic scripts/repair_review_label_provenance.py uses).
    assert discloses_non_human_review(disclosed_notes) is True

    repaired = repository.reclassify_review_label_provenance(
        "review-label-pre-fix-001",
        review_origin="agent_diagnostic",
        reviewer_identity=AGENT_IDENTITY,
        expected_current_review_origin=None,
    )
    assert repaired.review_origin == "agent_diagnostic"
    assert repaired.is_authoritative is False
    assert repaired.label == "ambiguous", "the repair never rewrites the recorded label/notes, only provenance"
    assert repaired.notes == disclosed_notes

    after = repository.get_visit(BIRD_VISIT_ID)
    assert after.review_status.value == "needs_review", "the repair must revert the truth it never should have established"
    assert after.reviewed_label is None

    # The unrelated real human correction is untouched.
    unrelated_visit = repository.get_visit(unrelated_visit_id)
    assert unrelated_visit.review_status.value == "reviewed"
    assert unrelated_visit.reviewed_label == "squirrel"
    assert unrelated.review_label.is_authoritative is True

    # Re-running the repair with a stale expectation fails loudly rather
    # than silently reapplying.
    with pytest.raises(ReviewProvenanceConflictError):
        repository.reclassify_review_label_provenance(
            "review-label-pre-fix-001",
            review_origin="agent_diagnostic",
            reviewer_identity=AGENT_IDENTITY,
            expected_current_review_origin="legacy_unattributed",
        )


def test_reclassify_requires_reviewer_identity_and_valid_origin(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")
    created = repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=BIRD_VISIT_ID, label="northern_cardinal")
    )

    with pytest.raises(ReviewProvenanceError):
        repository.reclassify_review_label_provenance(
            created.review_label.id, review_origin="agent_diagnostic", reviewer_identity="   "
        )


# --- Defense in depth: a human claim conflicting with its own disclosure ---


def test_human_origin_conflicting_with_self_disclosed_notes_is_rejected(tmp_path: Path) -> None:
    repository = repository_for(tmp_path / "db.sqlite3")
    with pytest.raises(ReviewProvenanceError):
        repository.create_review_label(
            ReviewCorrectionCreate(
                target_type="visit",
                target_id=BIRD_VISIT_ID,
                label="northern_cardinal",
                notes="[AGENT VISUAL REVIEW] looks like a cardinal",
                review_origin="human",
            )
        )
    # Nothing was persisted -- the visit remains exactly as it was.
    visit = repository.get_visit(BIRD_VISIT_ID)
    assert visit.review_status.value == "needs_review"
