"""Tier 1: the host's durable filesystem transport ledger.

Pure filesystem logic -- no FastAPI, no network. See
tests/test_camera_node_transport_router.py for the HTTP boundary and
tests/test_camera_node_transport_acceptance.py for the real end-to-end
proof.
"""

from __future__ import annotations

import hashlib

import pytest

from mockingbird.storage.camera_node_transport_ledger import TransportLedger, TransportLedgerError


def _ledger(tmp_path) -> TransportLedger:
    return TransportLedger(tmp_path / "transport")


def _declare(ledger, *, node_id="node-1", item_id="item-1", content_length=10, content_sha256=None, chunk_size=4):
    return ledger.declare(
        node_id=node_id,
        item_id=item_id,
        kind="evidence_capture",
        priority=100,
        media_type="image/jpeg",
        content_length=content_length,
        content_sha256=content_sha256 or hashlib.sha256(b"x" * content_length).hexdigest(),
        chunk_size=chunk_size,
        metadata={"camera_id": "cam-1"},
    )


def test_declare_new_item_reports_zero_received_bytes(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    received = _declare(ledger)
    assert received == 0
    assert not ledger.is_completed("node-1", "item-1")


def test_declare_is_idempotent_for_matching_signature(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    _declare(ledger)
    received_again = _declare(ledger)  # same node/item/content -- must not error
    assert received_again == 0


def test_declare_conflicting_signature_is_refused(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    _declare(ledger, content_length=10)
    with pytest.raises(TransportLedgerError) as excinfo:
        _declare(ledger, content_length=99, content_sha256="a" * 64)
    assert excinfo.value.error_code == "transport_item_conflict"
    assert excinfo.value.status_code == 409


def test_write_chunk_before_declare_is_unknown_item(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(TransportLedgerError) as excinfo:
        ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=b"abcd", declared_sha256=hashlib.sha256(b"abcd").hexdigest())
    assert excinfo.value.error_code == "transport_item_unknown"


def test_write_chunk_sequential_then_complete_roundtrips_exact_bytes(tmp_path) -> None:
    payload = b"0123456789"
    ledger = _ledger(tmp_path)
    _declare(ledger, content_length=len(payload), content_sha256=hashlib.sha256(payload).hexdigest(), chunk_size=4)
    for index, offset in enumerate(range(0, len(payload), 4)):
        chunk = payload[offset : offset + 4]
        received = ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=index, chunk=chunk, declared_sha256=hashlib.sha256(chunk).hexdigest())
        assert received == offset + len(chunk)
    ledger.complete(node_id="node-1", item_id="item-1")
    assert ledger.is_completed("node-1", "item-1")
    completed_bytes = (tmp_path / "transport" / "node-1" / "completed" / "item-1.bin").read_bytes()
    assert completed_bytes == payload


def test_write_chunk_hash_mismatch_is_rejected(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    _declare(ledger, chunk_size=4)
    with pytest.raises(TransportLedgerError) as excinfo:
        ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=b"abcd", declared_sha256="0" * 64)
    assert excinfo.value.error_code == "transport_chunk_hash_mismatch"


def test_write_chunk_out_of_order_gap_is_rejected(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    _declare(ledger, chunk_size=4)
    with pytest.raises(TransportLedgerError) as excinfo:
        ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=2, chunk=b"abcd", declared_sha256=hashlib.sha256(b"abcd").hexdigest())
    assert excinfo.value.error_code == "transport_chunk_out_of_order"


def test_write_chunk_retry_of_already_received_chunk_is_idempotent(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    _declare(ledger, chunk_size=4)
    ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=b"abcd", declared_sha256=hashlib.sha256(b"abcd").hexdigest())
    # Retried (e.g. response was lost) -- same chunk, must not double-append.
    received_again = ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=b"abcd", declared_sha256=hashlib.sha256(b"abcd").hexdigest())
    assert received_again == 4
    assert ledger.received_bytes("node-1", "item-1") == 4


def test_complete_before_all_bytes_received_is_refused(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    _declare(ledger, content_length=10, chunk_size=4)
    ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=b"abcd", declared_sha256=hashlib.sha256(b"abcd").hexdigest())
    with pytest.raises(TransportLedgerError) as excinfo:
        ledger.complete(node_id="node-1", item_id="item-1")
    assert excinfo.value.error_code == "transport_item_incomplete"


def test_complete_is_idempotent_after_success(tmp_path) -> None:
    payload = b"abcd"
    ledger = _ledger(tmp_path)
    _declare(ledger, content_length=4, content_sha256=hashlib.sha256(payload).hexdigest(), chunk_size=4)
    ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=payload, declared_sha256=hashlib.sha256(payload).hexdigest())
    ledger.complete(node_id="node-1", item_id="item-1")
    ledger.complete(node_id="node-1", item_id="item-1")  # ack was lost, Node retries -- must not raise


def test_write_chunk_after_completion_is_a_safe_noop(tmp_path) -> None:
    """The `complete` ack was lost; the Node retries a chunk it thinks is
    still outstanding. Nothing left to do, not an error."""

    payload = b"abcd"
    ledger = _ledger(tmp_path)
    _declare(ledger, content_length=4, content_sha256=hashlib.sha256(payload).hexdigest(), chunk_size=4)
    ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=payload, declared_sha256=hashlib.sha256(payload).hexdigest())
    ledger.complete(node_id="node-1", item_id="item-1")
    received = ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=payload, declared_sha256=hashlib.sha256(payload).hexdigest())
    assert received == 4


def test_complete_hash_mismatch_resets_progress_for_a_clean_resend(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    correct_payload = b"abcd"
    # Declare with the *correct* hash, but write different bytes (simulates
    # in-flight corruption) so complete-time verification fails.
    _declare(ledger, content_length=4, content_sha256=hashlib.sha256(correct_payload).hexdigest(), chunk_size=4)
    corrupted = b"abcx"
    ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=corrupted, declared_sha256=hashlib.sha256(corrupted).hexdigest())
    with pytest.raises(TransportLedgerError) as excinfo:
        ledger.complete(node_id="node-1", item_id="item-1")
    assert excinfo.value.error_code == "transport_item_hash_mismatch"
    assert excinfo.value.status_code == 422
    # Never promoted to completed/ -- an incomplete/corrupt transfer must
    # never become authoritative.
    assert not ledger.is_completed("node-1", "item-1")
    # The *next* declare reports received_bytes=0 -- a clean resend, not a
    # half-corrupted resume.
    received = _declare(ledger, content_length=4, content_sha256=hashlib.sha256(correct_payload).hexdigest(), chunk_size=4)
    assert received == 0


def test_declare_after_completion_with_matching_signature_is_a_clean_duplicate(tmp_path) -> None:
    payload = b"abcd"
    ledger = _ledger(tmp_path)
    digest = hashlib.sha256(payload).hexdigest()
    _declare(ledger, content_length=4, content_sha256=digest, chunk_size=4)
    ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=payload, declared_sha256=digest)
    ledger.complete(node_id="node-1", item_id="item-1")
    received = _declare(ledger, content_length=4, content_sha256=digest, chunk_size=4)
    assert received == 4


def test_declare_after_completion_with_conflicting_signature_is_refused(tmp_path) -> None:
    payload = b"abcd"
    ledger = _ledger(tmp_path)
    digest = hashlib.sha256(payload).hexdigest()
    _declare(ledger, content_length=4, content_sha256=digest, chunk_size=4)
    ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=payload, declared_sha256=digest)
    ledger.complete(node_id="node-1", item_id="item-1")
    with pytest.raises(TransportLedgerError) as excinfo:
        _declare(ledger, content_length=99, content_sha256="0" * 64, chunk_size=4)
    assert excinfo.value.error_code == "transport_item_conflict"


def test_status_reports_unknown_in_progress_and_completed(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    assert ledger.status(node_id="node-1", item_id="item-1") is None
    _declare(ledger, content_length=4, chunk_size=4, content_sha256=hashlib.sha256(b"abcd").hexdigest())
    in_progress = ledger.status(node_id="node-1", item_id="item-1")
    assert in_progress.state == "in_progress" and in_progress.received_bytes == 0
    ledger.write_chunk(node_id="node-1", item_id="item-1", chunk_index=0, chunk=b"abcd", declared_sha256=hashlib.sha256(b"abcd").hexdigest())
    ledger.complete(node_id="node-1", item_id="item-1")
    completed = ledger.status(node_id="node-1", item_id="item-1")
    assert completed.state == "completed" and completed.received_bytes == 4


def test_backlog_summary_roundtrips(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    assert ledger.read_backlog_summary("node-1") is None
    ledger.record_backlog_summary(node_id="node-1", summary={"pending_count": 3, "pending_bytes": 900})
    summary = ledger.read_backlog_summary("node-1")
    assert summary["pending_count"] == 3
    assert summary["pending_bytes"] == 900
    assert "reported_at" in summary


def test_invalid_node_id_is_rejected(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    with pytest.raises(TransportLedgerError) as excinfo:
        _declare(ledger, node_id="../escape")
    assert excinfo.value.error_code == "transport_node_id_invalid"


# --------------------------------------------------------------------------
# Appliance / Storage / Privacy / Recovery v1, Phase E: consumer-facing
# read/delete surface (list_node_ids, list_completed_item_ids,
# completed_item_metadata, completed_blob_path, delete_completed_item).
# --------------------------------------------------------------------------


def _complete(ledger, *, node_id="node-1", item_id="item-1", payload=b"x" * 10) -> None:
    content_sha256 = hashlib.sha256(payload).hexdigest()
    ledger.declare(
        node_id=node_id, item_id=item_id, kind="evidence_capture", priority=100, media_type="image/jpeg",
        content_length=len(payload), content_sha256=content_sha256, chunk_size=len(payload), metadata={},
    )
    ledger.write_chunk(node_id=node_id, item_id=item_id, chunk_index=0, chunk=payload, declared_sha256=content_sha256)
    ledger.complete(node_id=node_id, item_id=item_id)


def test_list_node_ids_is_empty_before_anything_exists(tmp_path) -> None:
    assert _ledger(tmp_path).list_node_ids() == []


def test_list_node_ids_and_completed_item_ids_reflect_real_completions(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    _complete(ledger, node_id="node-a", item_id="item-1")
    _complete(ledger, node_id="node-a", item_id="item-2")
    _complete(ledger, node_id="node-b", item_id="item-1")
    _declare(ledger, node_id="node-a", item_id="item-still-in-progress")  # never completed

    assert ledger.list_node_ids() == ["node-a", "node-b"]
    assert ledger.list_completed_item_ids("node-a") == ["item-1", "item-2"]
    assert ledger.list_completed_item_ids("node-b") == ["item-1"]


def test_completed_item_metadata_and_blob_path_resolve_only_once_completed(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    assert ledger.completed_item_metadata("node-1", "item-1") is None
    assert ledger.completed_blob_path("node-1", "item-1") is None

    _complete(ledger, payload=b"real-bytes")

    meta = ledger.completed_item_metadata("node-1", "item-1")
    assert meta is not None
    assert meta["content_length"] == len(b"real-bytes")
    blob_path = ledger.completed_blob_path("node-1", "item-1")
    assert blob_path is not None
    assert blob_path.read_bytes() == b"real-bytes"


def test_delete_completed_item_removes_blob_and_metadata_and_is_idempotent(tmp_path) -> None:
    ledger = _ledger(tmp_path)
    _complete(ledger)
    assert ledger.completed_blob_path("node-1", "item-1") is not None

    ledger.delete_completed_item("node-1", "item-1")

    assert ledger.completed_blob_path("node-1", "item-1") is None
    assert ledger.completed_item_metadata("node-1", "item-1") is None
    assert ledger.list_completed_item_ids("node-1") == []
    # Idempotent: calling it again on an already-gone item is a safe no-op.
    ledger.delete_completed_item("node-1", "item-1")
