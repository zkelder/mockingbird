"""Tier 1/2: Doctor's Camera Node transport check (Phase K).

`_interpret_camera_node_transport` is pure (hand-built `gathered` fixtures,
no real database) -- mirrors the exact established convention in
tests/test_doctor.py for every other `_interpret_*` function. One
integration test drives the real `run_doctor()` orchestrator end-to-end
through the actual pairing-config storage path.
"""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
from pathlib import Path

from mockingbird.api.schemas import CameraSourceCreate, SourceProviderConfigurationUpdate
from mockingbird.diagnostics import doctor
from mockingbird.diagnostics.doctor import DoctorCheckCode, DoctorStatus, run_doctor
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.camera_node_transport_ledger import TransportLedger


def test_interpret_no_transport_configured_anywhere_is_pass() -> None:
    result = doctor._interpret_camera_node_transport({"sources": []}, now=datetime.now(UTC))
    assert result.status == DoctorStatus.PASS
    assert "not in use" in result.detail


def test_interpret_transport_configured_but_never_contacted_warns() -> None:
    gathered = {
        "sources": [
            {"source_id": "s1", "name": "Backyard Node", "node_id": "node-abc", "transport_configured": True, "backlog_summary": None}
        ]
    }
    result = doctor._interpret_camera_node_transport(gathered, now=datetime.now(UTC))
    assert result.status == DoctorStatus.WARN
    assert result.diagnostic_context["sources"][0]["state"] == "never_contacted"


def test_interpret_fresh_backlog_clear_is_pass() -> None:
    now = datetime.now(UTC)
    gathered = {
        "sources": [
            {
                "source_id": "s1", "name": "Backyard Node", "node_id": "node-abc", "transport_configured": True,
                "backlog_summary": {"reported_at": now.timestamp() - 5, "pending_count": 0, "pending_bytes": 0, "failed_terminal_count": 0, "last_error": None},
            }
        ]
    }
    result = doctor._interpret_camera_node_transport(gathered, now=now)
    assert result.status == DoctorStatus.PASS
    assert result.diagnostic_context["sources"][0]["state"] == "reporting"


def test_interpret_fresh_backlog_pending_is_pass_but_named(now_factory=None) -> None:
    now = datetime.now(UTC)
    gathered = {
        "sources": [
            {
                "source_id": "s1", "name": "Backyard Node", "node_id": "node-abc", "transport_configured": True,
                "backlog_summary": {"reported_at": now.timestamp() - 5, "pending_count": 4, "pending_bytes": 40_000, "failed_terminal_count": 0, "last_error": None},
            }
        ]
    }
    result = doctor._interpret_camera_node_transport(gathered, now=now)
    assert result.status == DoctorStatus.PASS  # draining, not itself unhealthy
    assert "4 item(s) backlogged" in result.summary


def test_interpret_stale_last_contact_warns() -> None:
    now = datetime.now(UTC)
    gathered = {
        "sources": [
            {
                "source_id": "s1", "name": "Remote Node", "node_id": "node-abc", "transport_configured": True,
                "backlog_summary": {"reported_at": now.timestamp() - 7200, "pending_count": 2, "pending_bytes": 2000, "failed_terminal_count": 0, "last_error": "transport_host_unreachable"},
            }
        ]
    }
    result = doctor._interpret_camera_node_transport(gathered, now=now)
    assert result.status == DoctorStatus.WARN
    assert result.diagnostic_context["sources"][0]["state"] == "stale"


def test_interpret_failed_terminal_items_warns_distinctly() -> None:
    now = datetime.now(UTC)
    gathered = {
        "sources": [
            {
                "source_id": "s1", "name": "Node A", "node_id": "node-abc", "transport_configured": True,
                "backlog_summary": {"reported_at": now.timestamp() - 5, "pending_count": 0, "pending_bytes": 0, "failed_terminal_count": 3, "last_error": "transport_item_conflict"},
            }
        ]
    }
    result = doctor._interpret_camera_node_transport(gathered, now=now)
    assert result.status == DoctorStatus.WARN
    assert "cannot be delivered" in result.summary


def test_interpret_ignores_sources_without_transport_configured() -> None:
    gathered = {"sources": [{"source_id": "s1", "name": "Old Node", "node_id": "node-abc", "transport_configured": False, "backlog_summary": None}]}
    result = doctor._interpret_camera_node_transport(gathered, now=datetime.now(UTC))
    assert result.status == DoctorStatus.PASS
    assert "not in use" in result.detail


# --------------------------------------------------------------------------
# Appliance / Storage / Privacy / Recovery v1, Phase E: host-side unconsumed
# completed-transport-item visibility.
# --------------------------------------------------------------------------


def test_interpret_recently_completed_unconsumed_backlog_does_not_warn_yet() -> None:
    """Consumption is normally synchronous -- a brief window before the
    stale-contact threshold is not itself a problem."""

    now = datetime.now(UTC)
    gathered = {
        "sources": [
            {
                "source_id": "s1", "name": "Node A", "node_id": "node-abc", "transport_configured": True,
                "backlog_summary": {"reported_at": now.timestamp() - 5, "pending_count": 0, "pending_bytes": 0, "failed_terminal_count": 0, "last_error": None},
            }
        ],
        "unconsumed_count": 2,
        "unconsumed_bytes": 4000,
        "oldest_unconsumed_completed_at": now.timestamp() - 30,
    }
    result = doctor._interpret_camera_node_transport(gathered, now=now)
    assert result.status == DoctorStatus.PASS
    assert result.diagnostic_context["unconsumed_count"] == 2


def test_interpret_stuck_unconsumed_backlog_warns() -> None:
    now = datetime.now(UTC)
    gathered = {
        "sources": [
            {
                "source_id": "s1", "name": "Node A", "node_id": "node-abc", "transport_configured": True,
                "backlog_summary": {"reported_at": now.timestamp() - 5, "pending_count": 0, "pending_bytes": 0, "failed_terminal_count": 0, "last_error": None},
            }
        ],
        "unconsumed_count": 3,
        "unconsumed_bytes": 9000,
        "oldest_unconsumed_completed_at": now.timestamp() - 7200,
    }
    result = doctor._interpret_camera_node_transport(gathered, now=now)
    assert result.status == DoctorStatus.WARN
    assert "not been consumed" in result.summary


def test_interpret_unattributed_unconsumed_backlog_warns_even_with_no_configured_sources() -> None:
    """A completed transport item with no currently-configured Source (for
    example after an interrupted Camera Node replacement) must never be
    silently invisible just because no Source reads as `transport_
    configured` right now."""

    gathered = {"sources": [], "unconsumed_count": 1, "unconsumed_bytes": 2000}
    result = doctor._interpret_camera_node_transport(gathered, now=datetime.now(UTC))
    assert result.status == DoctorStatus.WARN
    assert "not attributed to any configured Source" in result.summary


def test_scan_unconsumed_backlog_reflects_real_ledger_state(tmp_path: Path) -> None:
    ledger = TransportLedger(tmp_path / "transport")
    payload = b"unconsumed-evidence-bytes"
    content_sha256 = hashlib.sha256(payload).hexdigest()
    ledger.declare(
        node_id="node-a", item_id="item-1", kind="evidence_capture", priority=100, media_type="image/jpeg",
        content_length=len(payload), content_sha256=content_sha256, chunk_size=len(payload), metadata={},
    )
    ledger.write_chunk(node_id="node-a", item_id="item-1", chunk_index=0, chunk=payload, declared_sha256=content_sha256)
    ledger.complete(node_id="node-a", item_id="item-1")

    result = doctor._scan_camera_node_transport_unconsumed_backlog(tmp_path / "transport")
    assert result["unconsumed_count"] == 1
    assert result["unconsumed_bytes"] == len(payload)
    assert result["oldest_unconsumed_completed_at"] is not None

    ledger.delete_completed_item("node-a", "item-1")
    cleared = doctor._scan_camera_node_transport_unconsumed_backlog(tmp_path / "transport")
    assert cleared == {"unconsumed_count": 0, "unconsumed_bytes": 0, "oldest_unconsumed_completed_at": None}


def test_run_doctor_surfaces_a_real_paired_transport_source(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    media_root = data_dir / "media" / "imports"
    media_root.mkdir(parents=True)
    db_path = data_dir / "mockingbird.sqlite3"
    repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=media_root)
    try:
        created = repository.create_camera_source(CameraSourceCreate(name="Yard Node"))
        repository.update_source_provider_configuration(
            created.source.id,
            SourceProviderConfigurationUpdate(
                provider_key="camera_node",
                config={
                    "node_base_address": "http://192.168.1.50:8787",
                    "node_credential": "pairing-credential-value",
                    "node_transport_credential": "transport-credential-value",
                    "node_camera_id": "cam-1",
                    "node_id": "node-real-abc123",
                    "node_pairing_state": "paired",
                },
            ),
        )
        ledger = TransportLedger(data_dir / "camera_node_transport")
        ledger.record_backlog_summary(node_id="node-real-abc123", summary={"pending_count": 2, "pending_bytes": 4000, "failed_terminal_count": 0, "last_error": None})
    finally:
        repository.close()

    report = run_doctor(runtime_home=tmp_path)
    check = next(item for item in report.checks if item.code == DoctorCheckCode.CAMERA_NODE_TRANSPORT)
    assert check.status == DoctorStatus.PASS
    assert check.diagnostic_context["sources"][0]["node_id"] == "node-real-abc123"
    assert check.diagnostic_context["sources"][0]["pending_count"] == 2
    # The real transport credential value must never surface in Doctor output.
    serialized = report.model_dump_json()
    assert "transport-credential-value" not in serialized
