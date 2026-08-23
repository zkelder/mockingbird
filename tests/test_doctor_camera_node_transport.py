"""Tier 1/2: Doctor's Camera Node transport check (Phase K).

`_interpret_camera_node_transport` is pure (hand-built `gathered` fixtures,
no real database) -- mirrors the exact established convention in
tests/test_doctor.py for every other `_interpret_*` function. One
integration test drives the real `run_doctor()` orchestrator end-to-end
through the actual pairing-config storage path.
"""

from __future__ import annotations

from datetime import UTC, datetime
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
