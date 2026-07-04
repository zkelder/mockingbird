"""Disabled worker metadata for future automation status."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from mockingbird.api.schemas import WorkerStatusItem


@dataclass(frozen=True, slots=True)
class WorkerDefinition:
    worker_key: str
    display_name: str
    category: str
    provider_key: str | None
    source_id: str | None
    stream_id: str | None
    message: str
    warnings: tuple[str, ...]


WORKER_DEFINITIONS: tuple[WorkerDefinition, ...] = (
    WorkerDefinition(
        worker_key="external_url_preview_scheduler_future",
        display_name="External URL preview scheduler",
        category="provider",
        provider_key="external_url",
        source_id=None,
        stream_id=None,
        message=(
            "Future scheduled preview visibility only; no external URL fetch, "
            "media creation, evidence creation, or truth creation exists."
        ),
        warnings=("Worker runtime is not implemented in this phase.",),
    ),
    WorkerDefinition(
        worker_key="folder_import_scan_future",
        display_name="Folder import scan",
        category="provider",
        provider_key="folder_import_future",
        source_id=None,
        stream_id=None,
        message=(
            "Future folder scan visibility only; no watcher, polling, folder "
            "scan, media creation, evidence creation, or truth creation exists."
        ),
        warnings=("Worker runtime is not implemented in this phase.",),
    ),
    WorkerDefinition(
        worker_key="webhook_ingest_queue_future",
        display_name="Webhook ingest queue",
        category="provider_ingest",
        provider_key="webhook_future",
        source_id=None,
        stream_id=None,
        message=(
            "Future webhook queue visibility only; no async queue, payload "
            "processing, media creation, evidence creation, or truth creation exists."
        ),
        warnings=("Worker runtime is not implemented in this phase.",),
    ),
    WorkerDefinition(
        worker_key="saved_media_retention_future",
        display_name="Saved media retention",
        category="retention",
        provider_key=None,
        source_id=None,
        stream_id=None,
        message=(
            "Future retention job visibility only; no background cleanup, "
            "record deletion, media deletion, or truth mutation exists."
        ),
        warnings=("Worker runtime is not implemented in this phase.",),
    ),
    WorkerDefinition(
        worker_key="model_suggestion_job_future",
        display_name="Model suggestion job",
        category="model_suggestion",
        provider_key=None,
        source_id=None,
        stream_id=None,
        message=(
            "Future suggestion job visibility only; no model runtime, "
            "DetectionProposal, SpeciesSuggestion, media, or truth creation exists."
        ),
        warnings=("Worker runtime is not implemented in this phase.",),
    ),
)


def list_worker_status_items(now: datetime | None = None) -> list[WorkerStatusItem]:
    """Return disabled worker status metadata without executing worker behavior."""
    del now
    return [
        WorkerStatusItem(
            worker_key=definition.worker_key,
            display_name=definition.display_name,
            category=definition.category,
            state="disabled",
            enabled=False,
            implemented=False,
            provider_key=definition.provider_key,
            source_id=definition.source_id,
            stream_id=definition.stream_id,
            last_run_at=None,
            next_run_at=None,
            last_error=None,
            message=definition.message,
            can_create_media_assets=False,
            can_create_motion_evidence=False,
            can_create_events=False,
            can_create_visits=False,
            can_create_review_labels=False,
            can_create_truth=False,
            warnings=list(definition.warnings),
        )
        for definition in WORKER_DEFINITIONS
    ]


__all__ = ["WORKER_DEFINITIONS", "WorkerDefinition", "list_worker_status_items"]
