"""First-Run & Pairing Reliability v1: durable Camera Node pairing/setup.

Covers docs/camera-node-pairing-persistence-design.md's core promise: once a
Node accepts its one-time code, MockingBird must never strand it in "paired
somewhere but unusable here" for the rest of guided setup. These tests
exercise the durable `camera_node_pending_setups` record directly through
the same public `/api/camera-nodes/*` and `/api/camera-setup/*` routes the
browser uses -- simulating "refresh"/"restart" as a fresh, stateless HTTP
call or a brand-new `ProductRepository` against the same database file,
never anything held only in this test's own Python variables.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
import logging

import httpx
import pytest
from sqlalchemy import func, select

from mockingbird.api import main as api_main
from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers.camera_node import CameraNodeClient
from mockingbird.storage.models import (
    CameraNodePendingSetupModel,
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    ReviewLabelModel,
    StreamModel,
    VisitModel,
)


NEVER_ECHO_CREDENTIAL = "never-echo-node-credential"


class _FakeNodeRequester:
    """Local copy of the fixed-response fake Node used across the camera-node
    test suite (see tests/test_camera_node.py) -- duplicated rather than
    cross-imported to keep each test file self-contained, matching this
    repository's existing test convention."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.timings: list[object] = []

    def request(self, *, method, url, headers, body, max_bytes, timing):
        self.requests.append((method, url, headers))
        self.timings.append(timing)
        if url.endswith("/health"):
            return 200, {"Content-Type": "application/json"}, json.dumps({"node_id": "node-test", "display_name": "Test node", "api_version": "v1"}).encode()
        if url.endswith("/pair"):
            assert body and b"pairing_code" in body
            return 200, {"Content-Type": "application/json"}, json.dumps({
                "node_id": "node-test",
                "display_name": "Test node",
                "api_version": "v1",
                "credential": NEVER_ECHO_CREDENTIAL,
                "cameras": [{"camera_id": "opaque-camera-1", "display_name": "Feeder view", "status": "available", "snapshot_supported": True}],
            }).encode()
        if url.endswith("/pair/revoke"):
            return 204, {}, b""
        if url.endswith("/capabilities"):
            return 200, {"Content-Type": "application/json"}, json.dumps({"recommended_snapshot_timeout_seconds": 8.0}).encode()
        if url.endswith("/cameras"):
            return 200, {"Content-Type": "application/json"}, json.dumps({"items": [{"camera_id": "opaque-camera-1", "display_name": "Feeder view", "status": "available", "snapshot_supported": True, "provider_type": "v4l2"}]}).encode()
        if "/snapshot" in url:
            return 200, {"Content-Type": "image/jpeg"}, b"\xff\xd8fake\xff\xd9"
        return 404, {"Content-Type": "application/json"}, b"{}"


def _repository(tmp_path, *, name: str = "camera-node-pairing.sqlite3") -> ProductRepository:
    return ProductRepository(
        db_url=f"sqlite:///{tmp_path / name}",
        media_root=tmp_path / "media",
    )


def _counts(repository: ProductRepository) -> tuple[int, int, int, int, int]:
    with repository.session_factory() as session:
        return tuple(
            session.scalar(select(func.count(model.id))) or 0
            for model in (CameraSourceModel, StreamModel, EventModel, VisitModel, MediaAssetModel)
        )


def _pending_setup_row_count(repository: ProductRepository) -> int:
    with repository.session_factory() as session:
        return session.scalar(select(func.count(CameraNodePendingSetupModel.token))) or 0


def _zone_payload() -> list[dict]:
    return [{
        "name": "Feeder",
        "zone_type": "feeder",
        "polygon": [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}],
        "monitoring_policy": {"activity_sensitivity": "normal"},
    }]


def _complete_payload(*, token: str, camera_name: str, key: str) -> dict:
    return {
        "camera_name": camera_name,
        "stream_name": f"{camera_name} view",
        "provider_key": "camera_node",
        "config": {"node_camera_id": "opaque-camera-1"},
        "node_pairing_token": token,
        "zones": _zone_payload(),
        "enable_monitoring": False,
        "idempotency_key": key,
    }


class _AuthRejectingRequester(_FakeNodeRequester):
    """Simulates a Node that has genuinely rejected the stored credential --
    for example its own pairing.json was cleared -- for every authenticated
    call after pairing succeeds."""

    def request(self, **kwargs):
        if kwargs["url"].endswith("/cameras") or "/snapshot" in kwargs["url"]:
            return 401, {"Content-Type": "application/json"}, b'{"detail":"Pairing authentication is required."}'
        return super().request(**kwargs)


class _OneTimeCodeRequester(_FakeNodeRequester):
    """Mimics the Node's real one-time-code consumption (without a live
    async Node bridge) so duplicate-pair safety can be tested precisely."""

    def __init__(self) -> None:
        super().__init__()
        self._used_codes: set[str] = set()

    def request(self, **kwargs):
        if kwargs["url"].endswith("/pair"):
            code = json.loads(kwargs["body"])["pairing_code"]
            if code in self._used_codes:
                return 409, {"Content-Type": "application/json"}, b'{"detail":"Pairing code was already used."}'
            self._used_codes.add(code)
        return super().request(**kwargs)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _client_for(repository: ProductRepository, requester) -> httpx.AsyncClient:
    api_main._camera_node_client = CameraNodeClient(requester=requester)
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


async def _pair(client: httpx.AsyncClient, *, code: str = "correct-one-time-code") -> httpx.Response:
    return await client.post(
        "/api/camera-nodes/pair",
        json={"base_address": "http://127.0.0.1:8787", "pairing_code": code},
    )


def test_successful_pairing_is_persisted_before_the_response_is_sent(tmp_path) -> None:
    """The core design correction: the credential is durable server-side the
    instant the Node accepts the code -- not held only in an ephemeral
    in-memory handoff for the rest of the wizard."""

    repository = _repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _FakeNodeRequester()) as client:
            before = _counts(repository)
            response = await _pair(client)
            assert response.status_code == 200
            assert NEVER_ECHO_CREDENTIAL not in response.text
            token = response.json()["pairing_token"]
            # No React state, no sessionStorage, no in-memory dict: read it
            # straight back from the database this same process just wrote.
            with repository.session_factory() as session:
                row = session.get(CameraNodePendingSetupModel, token)
                assert row is not None
                assert row.credential == NEVER_ECHO_CREDENTIAL
                assert row.status == "active"
            assert _counts(repository) == before  # pairing alone creates no product records

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_refresh_immediately_after_pair_resumes_at_camera_selection(tmp_path) -> None:
    repository = _repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _FakeNodeRequester()) as client:
            paired = await _pair(client)
            original_token = paired.json()["pairing_token"]

            # "Refresh": a brand-new, stateless GET with nothing remembered
            # client-side except the fact that the wizard is on the camera
            # step -- exactly what a reloaded browser tab can still ask.
            resumed = await client.get("/api/camera-nodes/pending-setup")
            assert resumed.status_code == 200
            body = resumed.json()
            assert body["pairing_token"] == original_token
            assert body["status"] == "active"
            assert body["display_name"] == "Test node"
            assert any(camera["camera_id"] == "opaque-camera-1" for camera in body["cameras"])
            assert NEVER_ECHO_CREDENTIAL not in resumed.text

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_refresh_after_validation_resumes_without_re_pairing(tmp_path) -> None:
    repository = _repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _FakeNodeRequester()) as client:
            paired = await _pair(client)
            token = paired.json()["pairing_token"]
            validation = await client.post("/api/camera-setup/validate", json={
                "provider_key": "camera_node",
                "config": {"node_camera_id": "opaque-camera-1"},
                "node_pairing_token": token,
            })
            assert validation.status_code == 200
            assert validation.json()["can_continue"] is True

            resumed = await client.get("/api/camera-nodes/pending-setup")
            assert resumed.status_code == 200
            assert resumed.json()["pairing_token"] == token
            assert resumed.json()["status"] == "active"

            # Complete setup using only the token the "refreshed" resume
            # returned -- never the original in-memory pair() response.
            completed = await client.post(
                "/api/camera-setup/complete",
                json=_complete_payload(token=resumed.json()["pairing_token"], camera_name="Resumed camera", key="resume-after-validate"),
            )
            assert completed.status_code == 200

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_refresh_after_preview_resumes_and_preview_creates_no_truth(tmp_path) -> None:
    repository = _repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _FakeNodeRequester()) as client:
            before = _counts(repository)
            paired = await _pair(client)
            token = paired.json()["pairing_token"]
            preview = await client.post(
                "/api/camera-nodes/preview",
                json={"pairing_token": token, "camera_id": "opaque-camera-1"},
            )
            assert preview.status_code == 200
            assert _counts(repository) == before

            resumed = await client.get("/api/camera-nodes/pending-setup")
            assert resumed.status_code == 200
            assert resumed.json()["pairing_token"] == token

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_setup_completes_long_after_the_one_time_code_ttl_would_have_expired(tmp_path) -> None:
    """The pairing-code TTL governs code consumption only, never how long a
    human may take to finish configuring their camera afterward -- see
    "Expiry behavior" in docs/camera-node-pairing-persistence-design.md."""

    repository = _repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _FakeNodeRequester()) as client:
            paired = await _pair(client)
            token = paired.json()["pairing_token"]

            # Longer than the old 10-minute in-memory handoff would ever
            # have allowed. The durable record has no expiry field to race.
            long_ago = datetime.now(UTC) - timedelta(hours=6)
            with repository.session_factory() as session:
                with session.begin():
                    row = session.get(CameraNodePendingSetupModel, token)
                    row.created_at = long_ago
                    row.updated_at = long_ago

            completed = await client.post(
                "/api/camera-setup/complete",
                json=_complete_payload(token=token, camera_name="Slow setup camera", key="slow-setup"),
            )
            assert completed.status_code == 200
            assert completed.json()["source"]["name"] == "Slow setup camera"

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_app_restart_during_incomplete_setup_still_resumes(tmp_path) -> None:
    """A brand-new `ProductRepository` instance against the same database
    file is what an application restart actually looks like -- no process-
    global survives that, only what was written to disk."""

    db_path = tmp_path / "restart.sqlite3"
    first_repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=tmp_path / "media")

    async def pair_once() -> str:
        async with _client_for(first_repository, _FakeNodeRequester()) as client:
            paired = await _pair(client)
            return paired.json()["pairing_token"]

    try:
        token = asyncio.run(pair_once())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        first_repository.close()

    second_repository = ProductRepository(db_url=f"sqlite:///{db_path}", media_root=tmp_path / "media")
    try:
        resumed = second_repository.get_latest_camera_node_pending_setup()
        assert resumed is not None
        assert resumed.pairing_token == token
        assert resumed.credential == NEVER_ECHO_CREDENTIAL
        assert resumed.status == "active"
    finally:
        second_repository.close()


def test_paired_but_incomplete_resume_reports_continue_setup_message(tmp_path) -> None:
    repository = _repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _FakeNodeRequester()) as client:
            await _pair(client)
            resumed = await client.get("/api/camera-nodes/pending-setup")
            assert resumed.status_code == 200
            assert "continue setup" in resumed.json()["message"].lower()
            assert "enter" not in resumed.json()["message"].lower()

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_no_resumable_setup_is_an_honest_404_not_an_empty_success(tmp_path) -> None:
    repository = _repository(tmp_path)
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    try:
        async def scenario() -> None:
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
                response = await client.get("/api/camera-nodes/pending-setup")
                assert response.status_code == 404

        asyncio.run(scenario())
    finally:
        configure_repository(None)
        repository.close()


def test_leaving_setup_without_explicit_forget_preserves_the_pending_pairing(tmp_path) -> None:
    """"Discard setup" / navigating away / closing the tab never revokes --
    only the explicit "forget this Camera Node" action does. See "Pairing
    recovery UX" in docs/camera-node-pairing-persistence-design.md."""

    repository = _repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _FakeNodeRequester()) as client:
            await _pair(client)

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None

    assert _pending_setup_row_count(repository) == 1
    resumed = repository.get_latest_camera_node_pending_setup()
    assert resumed is not None
    assert resumed.status == "active"
    repository.close()


def test_explicit_forget_revokes_at_the_node_and_removes_the_pending_setup(tmp_path) -> None:
    repository = _repository(tmp_path)
    requester = _FakeNodeRequester()

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            paired = await _pair(client)
            token = paired.json()["pairing_token"]

            revoked = await client.post(
                "/api/camera-nodes/pending-setup/revoke",
                json={"pairing_token": token},
            )
            assert revoked.status_code == 204

            after = await client.get("/api/camera-nodes/pending-setup")
            assert after.status_code == 404

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    assert any(url.endswith("/pair/revoke") for _, url, _ in requester.requests)


def test_genuine_node_side_rejection_marks_pairing_needs_renewal(tmp_path) -> None:
    repository = _repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _AuthRejectingRequester()) as client:
            paired = await _pair(client)
            token = paired.json()["pairing_token"]

            completed = await client.post(
                "/api/camera-setup/complete",
                json=_complete_payload(token=token, camera_name="Rejected camera", key="rejected-camera"),
            )
            assert completed.status_code == 400
            assert "pairing is no longer accepted" in completed.json()["detail"].lower()

            resumed = await client.get("/api/camera-nodes/pending-setup")
            assert resumed.status_code == 200
            assert resumed.json()["status"] == "needs_renewal"
            assert "renewed" in resumed.json()["message"].lower()

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_renewing_a_rejected_pairing_preserves_already_entered_form_state(tmp_path) -> None:
    repository = _repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _AuthRejectingRequester()) as client:
            paired = await _pair(client)
            stale_token = paired.json()["pairing_token"]
            draft_saved = await client.patch(
                f"/api/camera-nodes/pending-setup/{stale_token}",
                json={
                    "camera_name": "Backyard feeder camera",
                    "stream_name": "Feeder view",
                    "zone_name": "Feeder zone",
                    "sensitivity": "high",
                },
            )
            assert draft_saved.status_code == 200
            assert draft_saved.json()["camera_name"] == "Backyard feeder camera"
            # Force renewal by making the stale credential rejected.
            await client.post(
                "/api/camera-setup/complete",
                json=_complete_payload(token=stale_token, camera_name="unused", key="force-rejection"),
            )
            needs_renewal = await client.get("/api/camera-nodes/pending-setup")
            assert needs_renewal.json()["status"] == "needs_renewal"

            renewed = await client.post("/api/camera-nodes/pair", json={
                "base_address": "http://127.0.0.1:8787",
                "pairing_code": "fresh-code-after-renewal",
                "renews_pairing_token": stale_token,
            })
            assert renewed.status_code == 200
            new_token = renewed.json()["pairing_token"]
            assert new_token != stale_token

            resumed = await client.get("/api/camera-nodes/pending-setup")
            assert resumed.status_code == 200
            assert resumed.json()["pairing_token"] == new_token
            assert resumed.json()["status"] == "active"
            assert resumed.json()["camera_name"] == "Backyard feeder camera"
            assert resumed.json()["stream_name"] == "Feeder view"
            assert resumed.json()["zone_name"] == "Feeder zone"
            assert resumed.json()["sensitivity"] == "high"

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    # The stale, rejected row must not linger forever as a second,
    # confusing "resumable" candidate.
    assert _pending_setup_row_count(repository) == 1


def test_duplicate_pair_with_the_same_code_fails_cleanly_without_losing_the_first(tmp_path) -> None:
    repository = _repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _OneTimeCodeRequester()) as client:
            first = await _pair(client, code="only-once-code")
            assert first.status_code == 200
            first_token = first.json()["pairing_token"]

            second = await _pair(client, code="only-once-code")
            assert second.status_code == 409
            assert "rejected" in second.json()["detail"].lower()

            # The first, genuinely successful pairing must still be intact
            # and resumable -- a redundant/duplicate click never loses it.
            resumed = await client.get("/api/camera-nodes/pending-setup")
            assert resumed.status_code == 200
            assert resumed.json()["pairing_token"] == first_token

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    assert _pending_setup_row_count(repository) == 1


def test_pairing_credential_absent_from_logs_across_the_full_setup_flow(tmp_path, caplog) -> None:
    repository = _repository(tmp_path)
    caplog.set_level(logging.DEBUG)

    async def scenario() -> None:
        async with _client_for(repository, _FakeNodeRequester()) as client:
            paired = await _pair(client)
            token = paired.json()["pairing_token"]
            await client.get("/api/camera-nodes/pending-setup")
            await client.post(
                "/api/camera-nodes/preview",
                json={"pairing_token": token, "camera_id": "opaque-camera-1"},
            )
            await client.post(
                "/api/camera-setup/complete",
                json=_complete_payload(token=token, camera_name="Logged camera", key="logging-safe-camera"),
            )

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    assert NEVER_ECHO_CREDENTIAL not in caplog.text


def test_completed_camera_node_setup_removes_the_now_redundant_pending_row(tmp_path) -> None:
    repository = _repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _FakeNodeRequester()) as client:
            paired = await _pair(client)
            token = paired.json()["pairing_token"]
            completed = await client.post(
                "/api/camera-setup/complete",
                json=_complete_payload(token=token, camera_name="Promoted camera", key="promoted-camera"),
            )
            assert completed.status_code == 200

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    assert _pending_setup_row_count(repository) == 0


def test_camera_node_setup_flow_creates_no_review_or_species_truth(tmp_path) -> None:
    """A fresh repository auto-seeds an illustrative demo graph (see
    docs/local-product-packaging-design.md), which may itself include a
    reviewed label -- so this asserts the pairing/setup flow leaves that
    count *unchanged*, not that it is zero."""

    repository = _repository(tmp_path)
    with repository.session_factory() as session:
        review_labels_before = session.scalar(select(func.count(ReviewLabelModel.id))) or 0

    async def scenario() -> None:
        async with _client_for(repository, _FakeNodeRequester()) as client:
            paired = await _pair(client)
            token = paired.json()["pairing_token"]
            await client.post(
                "/api/camera-nodes/preview",
                json={"pairing_token": token, "camera_id": "opaque-camera-1"},
            )
            await client.post(
                "/api/camera-setup/complete",
                json=_complete_payload(token=token, camera_name="Truth-safe camera", key="truth-safe-camera"),
            )

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None

    with repository.session_factory() as session:
        assert (session.scalar(select(func.count(ReviewLabelModel.id))) or 0) == review_labels_before
    repository.close()


def test_resolve_pending_pairing_never_mutates_status_on_a_plain_read(tmp_path) -> None:
    """Only an actual `authentication_rejected` response from the Node
    marks `needs_renewal` -- an ordinary resume/read must never manufacture
    that state on its own."""

    repository = _repository(tmp_path)
    try:
        from mockingbird.source_providers.camera_node import CameraNodeCamera, CameraNodePairing

        pairing = CameraNodePairing(
            base_address="http://127.0.0.1:8787",
            node_id="node-test",
            display_name="Test node",
            api_version="v1",
            credential=NEVER_ECHO_CREDENTIAL,
            cameras=[CameraNodeCamera("opaque-camera-1", "Feeder view", "available", True)],
            capability_fingerprint="fingerprint",
        )
        pending = repository.create_camera_node_pending_setup(pairing)
        for _ in range(5):
            resolved = repository.resolve_camera_node_pending_pairing(
                pending.pairing_token, camera_id="opaque-camera-1"
            )
            assert resolved is not None
        assert repository.get_camera_node_pending_setup(pending.pairing_token).status == "active"
    finally:
        repository.close()
