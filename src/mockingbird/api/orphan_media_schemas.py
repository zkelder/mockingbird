"""Product-level API shapes for the Orphan Media Integrity & Recovery surface.

Contract: docs/orphan-media-integrity-recovery-contract.md. Responses carry
managed-root-relative paths only (never the absolute media root) and counts a
normal user can read; raw detail stays in `incomplete_reasons`/`items[].code`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mockingbird.storage.orphan_media import (
    MAX_QUARANTINE_PATHS,
    OrphanMediaScanReport,
    OrphanQuarantineBatchSummary,
    OrphanQuarantineResult,
    OrphanRestoreResult,
)


class OrphanMediaFindingResponse(BaseModel):
    relative_path: str
    size_bytes: int = Field(ge=0)
    modified_at: datetime
    kind: Literal["unowned", "unsafe_entry"]


class OrphanMediaScanResponse(BaseModel):
    status: Literal["clean", "orphans_found", "incomplete"]
    complete: bool
    scanned_at: datetime
    files_examined: int = Field(ge=0)
    owned_files: int = Field(ge=0)
    orphan_count: int = Field(ge=0)
    orphan_bytes: int = Field(ge=0)
    recently_written_count: int = Field(ge=0)
    unsafe_entry_count: int = Field(ge=0)
    excluded_counts: dict[str, int] = Field(default_factory=dict)
    incomplete_reasons: list[str] = Field(default_factory=list)
    findings: list[OrphanMediaFindingResponse] = Field(default_factory=list)
    findings_truncated: bool = False
    message: str
    # A scan reads only; it never moves a file or changes a record.
    changed_anything: bool = False
    creates_review_truth: bool = False


class OrphanQuarantineRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: bool = False
    relative_paths: list[str] = Field(min_length=1, max_length=MAX_QUARANTINE_PATHS)


class OrphanQuarantineItemResponse(BaseModel):
    relative_path: str
    outcome: Literal["moved", "skipped", "failed"]
    code: str | None = None


class OrphanQuarantineResponse(BaseModel):
    status: Literal["completed", "partial", "failed", "nothing_to_move"]
    batch_id: str | None = None
    moved_count: int = Field(ge=0)
    skipped_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    moved_bytes: int = Field(ge=0)
    items: list[OrphanQuarantineItemResponse] = Field(default_factory=list)
    message: str
    creates_review_truth: bool = False


class OrphanQuarantineBatchResponse(BaseModel):
    batch_id: str
    created_at: datetime
    item_count: int = Field(ge=0)
    moved_count: int = Field(ge=0)
    restored_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    moved_bytes: int = Field(ge=0)


class OrphanQuarantineHistoryResponse(BaseModel):
    batches: list[OrphanQuarantineBatchResponse] = Field(default_factory=list)


class OrphanRestoreResponse(BaseModel):
    status: Literal["completed", "partial", "failed"]
    batch_id: str
    restored_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)
    items: list[OrphanQuarantineItemResponse] = Field(default_factory=list)
    message: str


def scan_message(report: OrphanMediaScanReport) -> str:
    if report.status == "incomplete":
        return (
            "The storage check could not finish, so nothing can be said about unowned media yet. "
            "Nothing was changed. Try again, or run the MockingBird doctor."
        )
    if report.status == "clean":
        return "Storage integrity checked. No unowned media found."
    return (
        f"{report.orphan_count} saved file(s) are not linked to any observation. Nothing was changed. "
        "You can move them to a recovery folder and move them back later."
    )


def scan_response(report: OrphanMediaScanReport) -> OrphanMediaScanResponse:
    return OrphanMediaScanResponse(
        status=report.status,  # type: ignore[arg-type]
        complete=report.complete,
        scanned_at=report.started_at,
        files_examined=report.files_examined,
        owned_files=report.owned_files,
        orphan_count=report.orphan_count,
        orphan_bytes=report.orphan_bytes,
        recently_written_count=report.recently_written_count,
        unsafe_entry_count=report.unsafe_entry_count,
        excluded_counts=report.excluded_counts,
        incomplete_reasons=report.incomplete_reasons,
        findings=[
            OrphanMediaFindingResponse(
                relative_path=item.relative_path,
                size_bytes=item.size_bytes,
                modified_at=item.modified_at,
                kind=item.kind,  # type: ignore[arg-type]
            )
            for item in report.findings
        ],
        findings_truncated=report.findings_truncated,
        message=scan_message(report),
    )


def quarantine_message(result: OrphanQuarantineResult) -> str:
    if result.status == "completed":
        return f"{result.moved_count} file(s) moved to the recovery folder. Nothing was deleted."
    if result.status == "partial":
        return (
            f"{result.moved_count} file(s) moved, {result.failed_count} could not be moved and were left in place. "
            "Nothing was deleted."
        )
    if result.status == "failed":
        return "No files were moved. Nothing was deleted."
    return "Nothing needed to move: none of the selected files are still unowned."


def quarantine_response(result: OrphanQuarantineResult) -> OrphanQuarantineResponse:
    return OrphanQuarantineResponse(
        status=result.status,  # type: ignore[arg-type]
        batch_id=result.batch_id,
        moved_count=result.moved_count,
        skipped_count=result.skipped_count,
        failed_count=result.failed_count,
        moved_bytes=result.moved_bytes,
        items=[OrphanQuarantineItemResponse(relative_path=i.relative_path, outcome=i.outcome, code=i.code) for i in result.items],  # type: ignore[arg-type]
        message=quarantine_message(result),
    )


def batch_response(summary: OrphanQuarantineBatchSummary) -> OrphanQuarantineBatchResponse:
    return OrphanQuarantineBatchResponse(
        batch_id=summary.batch_id,
        created_at=summary.created_at,
        item_count=summary.item_count,
        moved_count=summary.moved_count,
        restored_count=summary.restored_count,
        failed_count=summary.failed_count,
        moved_bytes=summary.moved_bytes,
    )


def restore_response(result: OrphanRestoreResult) -> OrphanRestoreResponse:
    if result.status == "completed":
        message = f"{result.restored_count} file(s) moved back to where they were."
    elif result.status == "partial":
        message = (
            f"{result.restored_count} file(s) moved back; {result.conflict_count} were left in the recovery folder "
            "because something new already uses that name."
        )
    else:
        message = "No files were moved back. They remain safely in the recovery folder."
    return OrphanRestoreResponse(
        status=result.status,  # type: ignore[arg-type]
        batch_id=result.batch_id,
        restored_count=result.restored_count,
        conflict_count=result.conflict_count,
        failed_count=result.failed_count,
        items=[OrphanQuarantineItemResponse(relative_path=i.relative_path, outcome=i.outcome, code=i.code) for i in result.items],  # type: ignore[arg-type]
        message=message,
    )
