from dataclasses import fields, is_dataclass
from datetime import UTC, datetime

from mockingbird.workers.registry import (
    WORKER_DEFINITIONS,
    WorkerDefinition,
    list_worker_status_items,
)

EXPECTED_WORKER_KEYS = {
    "external_url_preview_scheduler_future",
    "folder_import_scan_future",
    "webhook_ingest_queue_future",
    "saved_media_retention_future",
    "model_suggestion_job_future",
}

CREATE_TRUTH_FIELDS = (
    "can_create_media_assets",
    "can_create_motion_evidence",
    "can_create_events",
    "can_create_visits",
    "can_create_review_labels",
    "can_create_truth",
)


def test_worker_registry_definitions_are_unique_disabled_metadata() -> None:
    worker_keys = [definition.worker_key for definition in WORKER_DEFINITIONS]

    assert set(worker_keys) == EXPECTED_WORKER_KEYS
    assert len(worker_keys) == len(set(worker_keys))

    for definition in WORKER_DEFINITIONS:
        assert definition.worker_key.endswith("_future")
        assert definition.display_name
        assert definition.category
        assert definition.message
        assert definition.warnings == ("Worker runtime is not implemented in this phase.",)


def test_worker_registry_definitions_expose_no_runtime_behavior() -> None:
    assert is_dataclass(WorkerDefinition)

    field_names = {field.name for field in fields(WorkerDefinition)}
    assert field_names == {
        "worker_key",
        "display_name",
        "category",
        "provider_key",
        "source_id",
        "stream_id",
        "message",
        "warnings",
    }

    forbidden_names = {"run", "start", "enable", "enabled", "callback", "schedule"}
    assert field_names.isdisjoint(forbidden_names)
    for definition in WORKER_DEFINITIONS:
        for forbidden_name in forbidden_names:
            assert not hasattr(definition, forbidden_name)


def test_worker_status_listing_remains_disabled_no_truth_metadata() -> None:
    workers = list_worker_status_items(now=datetime(2026, 7, 4, tzinfo=UTC))

    assert {worker.worker_key for worker in workers} == EXPECTED_WORKER_KEYS

    for worker in workers:
        assert worker.state == "disabled"
        assert worker.enabled is False
        assert worker.implemented is False
        assert worker.last_run_at is None
        assert worker.next_run_at is None
        assert worker.last_error is None
        assert worker.source_id is None
        assert worker.stream_id is None
        assert "not implemented" in " ".join(worker.warnings)
        for field_name in CREATE_TRUTH_FIELDS:
            assert getattr(worker, field_name) is False


def test_worker_status_listing_returns_fresh_metadata_items() -> None:
    first = list_worker_status_items()
    first[0].warnings.append("mutated test warning")

    second = list_worker_status_items()

    assert "mutated test warning" not in second[0].warnings
