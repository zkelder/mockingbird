"""Tier 1: the Node's outbound declare/chunk/complete protocol client.

Against a scripted fake requester -- no real sockets, no ASGI app. See
tests/test_camera_node_transport_acceptance.py for the real, fault-injected
end-to-end proof over real sockets.
"""

from __future__ import annotations

import hashlib
import json

import pytest

from mockingbird_node.transport_client import (
    TERMINAL_TRANSPORT_ERROR_CODES,
    TransportClient,
    TransportClientError,
    classify_error,
)
from mockingbird_node.transport_spool import PRIORITY_NORMAL, SpoolItem


def _item(item_id="item-1", *, content_length=10, content_sha256=None) -> SpoolItem:
    return SpoolItem(
        item_id=item_id,
        kind="evidence_capture",
        priority=PRIORITY_NORMAL,
        media_type="image/jpeg",
        metadata={"camera_id": "cam-1"},
        content_length=content_length,
        content_sha256=content_sha256 or hashlib.sha256(b"x" * content_length).hexdigest(),
        state="transmitting",
        attempt_count=0,
        next_attempt_at=0.0,
        last_error=None,
        enqueued_at=0.0,
        updated_at=0.0,
    )


class _ScriptedRequester:
    def __init__(self, responses: list[tuple[int, dict, bytes]]) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def request(self, *, method, url, headers, body):
        self.calls.append({"method": method, "url": url, "headers": headers, "body": body})
        if not self._responses:
            raise AssertionError("no more scripted responses")
        return self._responses.pop(0)


def _json_response(status: int, payload: dict) -> tuple[int, dict, bytes]:
    return status, {"Content-Type": "application/json"}, json.dumps(payload).encode("utf-8")


def test_declare_new_item_returns_accepted_with_received_bytes() -> None:
    requester = _ScriptedRequester([_json_response(200, {"status": "accepted", "received_bytes": 0})])
    client = TransportClient(requester=requester)
    outcome = client.declare(
        base_address="http://host", credential="cred", node_id="node-1", item=_item(),
        chunk_size=1024, backlog_summary={},
    )
    assert outcome.duplicate is False
    assert outcome.received_bytes == 0
    call = requester.calls[0]
    assert call["headers"]["Authorization"] == "Bearer cred"
    body = json.loads(call["body"])
    assert body["node_id"] == "node-1"
    assert body["transport_protocol_version"] == "transport/v1"


def test_declare_duplicate_short_circuits() -> None:
    requester = _ScriptedRequester([_json_response(200, {"status": "duplicate"})])
    client = TransportClient(requester=requester)
    outcome = client.declare(
        base_address="http://host", credential="cred", node_id="node-1", item=_item(content_length=99),
        chunk_size=1024, backlog_summary={},
    )
    assert outcome.duplicate is True
    assert outcome.received_bytes == 99


@pytest.mark.parametrize(
    ("status", "body", "expected_code"),
    [
        (401, {}, "authentication_rejected"),
        (400, {"detail": {"error_code": "transport_protocol_unsupported"}}, "transport_protocol_unsupported"),
        (409, {"detail": {"error_code": "transport_item_conflict"}}, "transport_item_conflict"),
        (500, {}, "transport_host_error"),
        (404, {"detail": {"error_code": "transport_item_unknown"}}, "transport_item_unknown"),
    ],
)
def test_declare_error_classification(status, body, expected_code) -> None:
    requester = _ScriptedRequester([_json_response(status, body)])
    client = TransportClient(requester=requester)
    with pytest.raises(TransportClientError) as excinfo:
        client.declare(
            base_address="http://host", credential="cred", node_id="node-1", item=_item(),
            chunk_size=1024, backlog_summary={},
        )
    assert str(excinfo.value) == expected_code


def test_send_chunk_includes_sha256_header_and_returns_received_bytes() -> None:
    chunk = b"abc123"
    requester = _ScriptedRequester([_json_response(200, {"status": "received", "received_bytes": len(chunk)})])
    client = TransportClient(requester=requester)
    received = client.send_chunk(base_address="http://host", credential="cred", item_id="item-1", chunk_index=0, chunk=chunk)
    assert received == len(chunk)
    call = requester.calls[0]
    assert call["headers"]["X-MockingBird-Chunk-Sha256"] == hashlib.sha256(chunk).hexdigest()
    assert call["body"] == chunk
    assert "/chunks/0" in call["url"]


def test_complete_success() -> None:
    requester = _ScriptedRequester([_json_response(200, {"status": "completed"})])
    client = TransportClient(requester=requester)
    client.complete(base_address="http://host", credential="cred", item_id="item-1")  # must not raise


def test_complete_hash_mismatch_is_recoverable_not_terminal() -> None:
    requester = _ScriptedRequester(
        [_json_response(422, {"detail": {"error_code": "transport_item_hash_mismatch"}})]
    )
    client = TransportClient(requester=requester)
    with pytest.raises(TransportClientError) as excinfo:
        client.complete(base_address="http://host", credential="cred", item_id="item-1")
    assert str(excinfo.value) == "transport_item_hash_mismatch"
    assert "transport_item_hash_mismatch" not in TERMINAL_TRANSPORT_ERROR_CODES


def test_deliver_full_flow_sends_declare_then_chunks_then_complete() -> None:
    payload = b"0123456789"  # 10 bytes, chunk_size=4 -> 3 chunks (4,4,2)
    responses = [
        _json_response(200, {"status": "accepted", "received_bytes": 0}),
        _json_response(200, {"status": "received", "received_bytes": 4}),
        _json_response(200, {"status": "received", "received_bytes": 8}),
        _json_response(200, {"status": "received", "received_bytes": 10}),
        _json_response(200, {"status": "completed"}),
    ]
    requester = _ScriptedRequester(responses)
    client = TransportClient(requester=requester)
    client.deliver(
        base_address="http://host", credential="cred", node_id="node-1",
        item=_item(content_length=10, content_sha256=hashlib.sha256(payload).hexdigest()),
        payload=payload, chunk_size=4, backlog_summary={},
    )
    urls = [call["url"] for call in requester.calls]
    assert urls[0].endswith("/api/camera-nodes/transport/items")
    assert "/chunks/0" in urls[1] and "/chunks/1" in urls[2] and "/chunks/2" in urls[3]
    assert urls[4].endswith("/complete")


def test_deliver_resumes_from_declared_received_bytes() -> None:
    payload = b"0123456789"
    responses = [
        _json_response(200, {"status": "accepted", "received_bytes": 4}),  # host already has first chunk
        _json_response(200, {"status": "received", "received_bytes": 8}),
        _json_response(200, {"status": "received", "received_bytes": 10}),
        _json_response(200, {"status": "completed"}),
    ]
    requester = _ScriptedRequester(responses)
    client = TransportClient(requester=requester)
    client.deliver(
        base_address="http://host", credential="cred", node_id="node-1",
        item=_item(content_length=10, content_sha256=hashlib.sha256(payload).hexdigest()),
        payload=payload, chunk_size=4, backlog_summary={},
    )
    # Only 2 chunk calls (index 1, 2) -- chunk 0 was already durably received.
    chunk_urls = [call["url"] for call in requester.calls if "/chunks/" in call["url"]]
    assert len(chunk_urls) == 2
    assert not any(url.endswith("/chunks/0") for url in chunk_urls)
    assert chunk_urls[0].endswith("/chunks/1")
    assert chunk_urls[1].endswith("/chunks/2")


def test_deliver_duplicate_sends_no_chunks_and_no_complete() -> None:
    requester = _ScriptedRequester([_json_response(200, {"status": "duplicate"})])
    client = TransportClient(requester=requester)
    client.deliver(
        base_address="http://host", credential="cred", node_id="node-1",
        item=_item(content_length=10), payload=b"0123456789", chunk_size=4, backlog_summary={},
    )
    assert len(requester.calls) == 1  # declare only


def test_classify_error_terminal_vs_retryable() -> None:
    assert classify_error(TransportClientError("transport_item_conflict")) == "terminal"
    assert classify_error(TransportClientError("transport_host_unreachable")) == "retryable"
    assert classify_error(TransportClientError("authentication_rejected")) == "retryable"
    assert classify_error(TransportClientError("transport_protocol_unsupported")) == "retryable"


def test_pacing_sleeps_proportional_to_configured_rate(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("mockingbird_node.transport_client.time.sleep", lambda seconds: sleeps.append(seconds))
    payload = b"x" * 100
    responses = [
        _json_response(200, {"status": "accepted", "received_bytes": 0}),
        _json_response(200, {"status": "received", "received_bytes": 100}),
        _json_response(200, {"status": "completed"}),
    ]
    client = TransportClient(requester=_ScriptedRequester(responses))
    client.deliver(
        base_address="http://host", credential="cred", node_id="node-1",
        item=_item(content_length=100, content_sha256=hashlib.sha256(payload).hexdigest()),
        payload=payload, chunk_size=100, backlog_summary={}, max_bytes_per_second=50,
    )
    assert sleeps == [pytest.approx(2.0)]  # 100 bytes at 50 B/s == 2s


def test_pacing_disabled_by_default_never_sleeps(monkeypatch) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("mockingbird_node.transport_client.time.sleep", lambda seconds: sleeps.append(seconds))
    payload = b"x" * 100
    responses = [
        _json_response(200, {"status": "accepted", "received_bytes": 0}),
        _json_response(200, {"status": "received", "received_bytes": 100}),
        _json_response(200, {"status": "completed"}),
    ]
    client = TransportClient(requester=_ScriptedRequester(responses))
    client.deliver(
        base_address="http://host", credential="cred", node_id="node-1",
        item=_item(content_length=100, content_sha256=hashlib.sha256(payload).hexdigest()),
        payload=payload, chunk_size=100, backlog_summary={},
    )
    assert sleeps == []
