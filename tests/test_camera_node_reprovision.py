"""Camera Node Configuration Backup + Reprovision / Replacement Recovery v1.

Covers the genuine physical-hardware-swap case that
tests/test_camera_node_repair_pairing.py deliberately does not: attaching a
*different* physical Camera Node (a different `node_id` -- the Node's own
`sha256(display_name)` identity, see `mockingbird_node/app.py`) onto an
existing, already-paired camera's Source/Stream, rather than only recovering
a lost credential for the *same* Node identity.

These tests exercise the same public `/api/camera-nodes/*` and
`/api/streams/{id}/camera-configuration/*` routes the browser uses, reusing
test_camera_node_repair_pairing.py's `_StatefulNodeRequester`/harness
conventions (that file already proves the same-identity repair path in
depth; this file deliberately does not duplicate that coverage).

See docs/camera-node-reprovision-recovery-design.md.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
import uuid

import httpx
import pytest
from sqlalchemy import select

from mockingbird.api import main as api_main
from mockingbird.api.main import app, configure_repository
from mockingbird.diagnostics import doctor
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers.camera_node import CameraNodeClient
from mockingbird.storage.models import CameraSourceModel, EventModel, ReviewLabelModel, VisitModel, ZoneModel


NEVER_ECHO_OLD_CREDENTIAL = "never-echo-old-hardware-credential"
NEVER_ECHO_NEW_CREDENTIAL = "never-echo-new-hardware-credential"
BASE_ADDRESS = "http://192.168.1.112:8787"


class _StatefulNodeRequester:
    """Mirrors tests/test_camera_node_repair_pairing.py's fake Node exactly,
    duplicated locally by this codebase's own established convention
    (per-file, hermetic, no shared Camera Node test fixture module)."""

    def __init__(self, *, correct_code: str, credential: str = NEVER_ECHO_OLD_CREDENTIAL, node_id: str = "node-original-pi") -> None:
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.correct_code = correct_code
        self.credential = credential
        self.node_id = node_id
        self.consumed = False
        self.authenticated = True

    def request(self, *, method, url, headers, body, max_bytes, timing):
        self.requests.append((method, url, headers))
        if url.endswith("/health"):
            return 200, {"Content-Type": "application/json"}, json.dumps(
                {"node_id": self.node_id, "display_name": "Feeder Node", "api_version": "v1"}
            ).encode()
        if url.endswith("/pair") and method == "POST":
            code = json.loads(body)["pairing_code"]
            if self.consumed:
                return 409, {"Content-Type": "application/json"}, b'{"detail":"Pairing code was already used."}'
            if code != self.correct_code:
                return 401, {"Content-Type": "application/json"}, b'{"detail":"Pairing code was rejected."}'
            self.consumed = True
            return 200, {"Content-Type": "application/json"}, json.dumps({
                "node_id": self.node_id,
                "display_name": "Feeder Node",
                "api_version": "v1",
                "credential": self.credential,
                "cameras": [{
                    "camera_id": "opaque-camera-1",
                    "display_name": "Feeder view",
                    "status": "available",
                    "snapshot_supported": True,
                }],
            }).encode()
        if url.endswith("/pair/revoke"):
            return 204, {}, b""
        if url.endswith("/capabilities"):
            return 200, {"Content-Type": "application/json"}, json.dumps(
                {"recommended_snapshot_timeout_seconds": 8.0}
            ).encode()
        if url.endswith("/cameras"):
            if not self.authenticated:
                return 401, {"Content-Type": "application/json"}, b'{"detail":"Pairing authentication is required."}'
            return 200, {"Content-Type": "application/json"}, json.dumps({"items": [{
                "camera_id": "opaque-camera-1",
                "display_name": "Feeder view",
                "status": "available",
                "snapshot_supported": True,
                "provider_type": "v4l2",
            }]}).encode()
        if "/snapshot" in url:
            return 200, {"Content-Type": "image/jpeg"}, b"\xff\xd8fake\xff\xd9"
        return 404, {"Content-Type": "application/json"}, b"{}"


def _repository(tmp_path, *, name: str = "camera-node-reprovision.sqlite3") -> ProductRepository:
    return ProductRepository(
        db_url=f"sqlite:///{tmp_path / name}",
        media_root=tmp_path / "media",
    )


def _client_for(repository: ProductRepository, requester: _StatefulNodeRequester) -> httpx.AsyncClient:
    api_main._camera_node_client = CameraNodeClient(requester=requester)
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://testserver")


def _zone_payload() -> list[dict]:
    return [{
        "name": "Feeder",
        "zone_type": "feeder",
        "polygon": [{"x": 0.2, "y": 0.2}, {"x": 0.8, "y": 0.2}, {"x": 0.8, "y": 0.8}, {"x": 0.2, "y": 0.8}],
        "monitoring_policy": {"activity_sensitivity": "normal"},
    }]


async def _pair(client: httpx.AsyncClient, *, code: str) -> httpx.Response:
    return await client.post(
        "/api/camera-nodes/pair",
        json={"base_address": BASE_ADDRESS, "pairing_code": code},
    )


async def _first_run_complete(client: httpx.AsyncClient, *, code: str) -> dict:
    paired = await _pair(client, code=code)
    assert paired.status_code == 200, paired.text
    token = paired.json()["pairing_token"]
    completed = await client.post("/api/camera-setup/complete", json={
        "camera_name": "Pi camera 1",
        "stream_name": "feeder",
        "provider_key": "camera_node",
        "config": {"node_camera_id": "opaque-camera-1"},
        "node_pairing_token": token,
        "zones": _zone_payload(),
        "enable_monitoring": False,
        "idempotency_key": "first-run-complete",
    })
    assert completed.status_code == 200, completed.text
    return completed.json()


def _payload(
    *,
    pairing_token: str,
    state_token: str,
    camera_id: str = "opaque-camera-1",
    confirm_node_identity_change: bool = False,
    replacement_reason: "str | None" = None,
) -> dict:
    return {
        "provider_key": "camera_node",
        "config": {"node_camera_id": camera_id},
        "secret_actions": {},
        "node_pairing_token": pairing_token,
        "source_name": None,
        "stream_name": None,
        "expected_state_token": state_token,
        "confirm_node_identity_change": confirm_node_identity_change,
        "replacement_reason": replacement_reason,
    }


async def _pair_different_hardware(client: httpx.AsyncClient, requester: _StatefulNodeRequester) -> str:
    """Simulates the SD card dying and a brand-new Pi being installed in its
    place: a different `node_id` (see `mockingbird_node/app.py`'s
    `node_id = sha256(display_name)`), a fresh credential, reachable at the
    same physical address."""

    requester.node_id = "node-replacement-pi"
    requester.correct_code = "replacement-code"
    requester.consumed = False
    requester.credential = NEVER_ECHO_NEW_CREDENTIAL
    paired = await _pair(client, code="replacement-code")
    assert paired.status_code == 200, paired.text
    return paired.json()["pairing_token"]


def test_unconfirmed_different_node_identity_is_still_rejected(tmp_path) -> None:
    """Safety default preserved: a different physical Node answering for an
    already-paired camera is ordinarily a mistake and must stay blocked
    without an explicit, deliberate confirmation."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code")

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]

            token = await _pair_different_hardware(client, requester)
            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            payload = _payload(pairing_token=token, state_token=edit.json()["state_token"])

            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json=payload)
            assert preview.status_code == 400, preview.text
            assert "different identity" in preview.json()["detail"].lower()
            assert "confirm" in preview.json()["detail"].lower()

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_confirmed_replacement_attaches_new_hardware_preserves_source_stream_zones(tmp_path) -> None:
    """The core capability: a confirmed hardware swap reattaches new
    physical infrastructure to the *existing* logical Source/Stream --
    never creating a second, duplicate camera."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code")
    ids: dict = {}

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]
            source_id = completion["source"]["id"]
            ids["stream_id"] = stream_id
            ids["source_id"] = source_id

            token = await _pair_different_hardware(client, requester)
            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            payload = _payload(
                pairing_token=token,
                state_token=edit.json()["state_token"],
                confirm_node_identity_change=True,
                replacement_reason="Original Pi's SD card failed",
            )

            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json=payload)
            assert preview.status_code == 200, preview.text
            impact = preview.json()["node_identity_replacement"]
            assert impact is not None
            assert impact["zones_review_recommended"] is True
            assert impact["new_node_id"] != impact["previous_node_id"]
            assert NEVER_ECHO_NEW_CREDENTIAL not in preview.text

            applied = await client.post(
                f"/api/streams/{stream_id}/camera-configuration/apply",
                json={
                    **payload,
                    "preview_token": preview.json()["preview_token"],
                    "idempotency_key": "replacement-apply-001",
                    "restart_monitoring": False,
                },
            )
            assert applied.status_code == 200, applied.text
            assert NEVER_ECHO_NEW_CREDENTIAL not in applied.text
            body = applied.json()
            # Same logical Source/Stream identity -- never a second, duplicate camera.
            assert body["configuration"]["source_id"] == source_id
            assert body["configuration"]["stream_id"] == stream_id
            assert body["configuration"]["hardware_replacement"]["reason"] == "Original Pi's SD card failed"
            assert "confirmed" in body["message"].lower()
            assert "zone" in body["message"].lower()

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    with repository.session_factory() as session:
        source = session.get(CameraSourceModel, ids["source_id"])
        assert source is not None
        assert source.id == ids["source_id"]  # never a new row
        zones = session.query(ZoneModel).filter_by(stream_id=ids["stream_id"]).all()
        assert [zone.name for zone in zones] == ["Feeder"]
    repository.close()


def test_confirmed_replacement_records_provenance_and_clears_prior_boot_facts(tmp_path) -> None:
    """Bounded provenance (prior node_id, transition timestamp, reason) is
    recorded, and the *prior* physical node's boot-identity facts are
    cleared rather than left to misleadingly describe the new hardware --
    the next real checkpoint against the new Node repopulates them
    honestly."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code", node_id="node-original-pi")
    ids: dict = {}

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]
            ids["source_id"] = completion["source"]["id"]

            with repository.session_factory() as session:
                source = session.get(CameraSourceModel, ids["source_id"])
                source.camera_node_boot_id = "boot-from-the-original-pi"
                source.camera_node_last_seen_at = datetime.now(UTC)
                source.camera_node_boot_first_seen_at = datetime.now(UTC)
                source.camera_node_recent_boot_transitions_json = json.dumps(
                    [{"boot_id": "boot-from-the-original-pi", "first_seen_at": datetime.now(UTC).isoformat()}]
                )
                session.commit()

            token = await _pair_different_hardware(client, requester)
            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            payload = _payload(
                pairing_token=token,
                state_token=edit.json()["state_token"],
                confirm_node_identity_change=True,
                replacement_reason="Replaced with a Pi 5",
            )
            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json=payload)
            applied = await client.post(
                f"/api/streams/{stream_id}/camera-configuration/apply",
                json={**payload, "preview_token": preview.json()["preview_token"], "idempotency_key": "provenance-apply-001", "restart_monitoring": False},
            )
            assert applied.status_code == 200, applied.text

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    with repository.session_factory() as session:
        source = session.get(CameraSourceModel, ids["source_id"])
        assert source.camera_node_prior_node_id == "node-original-pi"
        assert source.camera_node_identity_replaced_at is not None
        assert source.camera_node_replacement_reason == "Replaced with a Pi 5"
        # The prior physical node's boot facts must not be misattributed to
        # the replacement hardware -- honestly "not tracked yet" until the
        # new Node's own first real checkpoint.
        assert source.camera_node_boot_id is None
        assert source.camera_node_last_seen_at is None
        assert source.camera_node_boot_first_seen_at is None
        assert source.camera_node_recent_boot_transitions_json is None
    repository.close()


def test_reviewed_history_and_zones_unchanged_across_replacement(tmp_path) -> None:
    """Reviewed truth and Visit history predating a hardware replacement
    must survive it completely unchanged -- the whole product promise this
    milestone exists to keep."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code")
    ids: dict = {}

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]
            ids["stream_id"] = stream_id
            ids["source_id"] = completion["source"]["id"]

            event_id = f"event-{uuid.uuid4().hex[:12]}"
            visit_id = f"visit-{uuid.uuid4().hex[:12]}"
            with repository.session_factory() as session:
                session.add(EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title="Feeder activity",
                    event_type="activity_session",
                    started_at=datetime.now(UTC) - timedelta(days=1),
                    review_status="reviewed",
                ))
                session.add(VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="bird",
                    reviewed_label="northern_cardinal",
                    review_status="reviewed",
                    is_superseded=False,
                ))
                session.add(ReviewLabelModel(
                    id=f"review-{uuid.uuid4().hex[:12]}",
                    target_type="visit",
                    target_id=visit_id,
                    label="northern_cardinal",
                    created_at=datetime.now(UTC) - timedelta(days=1),
                ))
                session.commit()
            ids["visit_id"] = visit_id
            ids["event_id"] = event_id

            token = await _pair_different_hardware(client, requester)
            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            payload = _payload(
                pairing_token=token, state_token=edit.json()["state_token"], confirm_node_identity_change=True,
            )
            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json=payload)
            applied = await client.post(
                f"/api/streams/{stream_id}/camera-configuration/apply",
                json={**payload, "preview_token": preview.json()["preview_token"], "idempotency_key": "history-apply-001", "restart_monitoring": False},
            )
            assert applied.status_code == 200, applied.text

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    with repository.session_factory() as session:
        visit = session.get(VisitModel, ids["visit_id"])
        assert visit is not None
        assert visit.event_id == ids["event_id"]
        assert visit.reviewed_label == "northern_cardinal"
        assert visit.review_status == "reviewed"
        event = session.get(EventModel, ids["event_id"])
        assert event is not None
        assert event.stream_id == ids["stream_id"]
        review = session.scalar(
            select(ReviewLabelModel).where(
                ReviewLabelModel.target_type == "visit", ReviewLabelModel.target_id == ids["visit_id"]
            )
        )
        assert review is not None
        assert review.label == "northern_cardinal"
        zones = session.query(ZoneModel).filter_by(stream_id=ids["stream_id"]).all()
        assert [zone.name for zone in zones] == ["Feeder"]
    repository.close()


def test_ordinary_same_identity_repair_never_touches_replacement_provenance(tmp_path) -> None:
    """boot_id is per-boot and never part of logical identity (milestone
    instruction #18): an ordinary reboot/credential-repair of the *same*
    Node (same node_id) must never be treated as, or recorded as, a
    hardware replacement."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code", node_id="node-original-pi")
    ids: dict = {}

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]
            ids["source_id"] = completion["source"]["id"]

            await client.post("/api/camera-nodes/pair/revoke", json={"stream_id": stream_id})
            # Same physical Node (same node_id), only its credential changed --
            # simulates a plain reboot that cleared in-process pairing state.
            requester.correct_code = "repair-code"
            requester.consumed = False
            requester.credential = "same-hardware-new-credential"
            paired = await _pair(client, code="repair-code")
            token = paired.json()["pairing_token"]

            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            payload = _payload(pairing_token=token, state_token=edit.json()["state_token"])
            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json=payload)
            assert preview.status_code == 200, preview.text
            assert preview.json()["node_identity_replacement"] is None

            applied = await client.post(
                f"/api/streams/{stream_id}/camera-configuration/apply",
                json={**payload, "preview_token": preview.json()["preview_token"], "idempotency_key": "same-identity-apply-001", "restart_monitoring": False},
            )
            assert applied.status_code == 200, applied.text
            assert applied.json()["configuration"]["hardware_replacement"] is None

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    with repository.session_factory() as session:
        source = session.get(CameraSourceModel, ids["source_id"])
        assert source.camera_node_identity_replaced_at is None
        assert source.camera_node_prior_node_id is None
    repository.close()


def test_interrupted_replacement_leaves_old_source_recoverable(tmp_path) -> None:
    """A replacement interrupted before apply (a stale preview token, e.g. a
    second browser tab racing ahead) must never partially mutate the
    Source -- the existing transactional apply already guarantees this; this
    proves it holds for the new confirm_node_identity_change path too."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code")
    ids: dict = {}

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]
            ids["source_id"] = completion["source"]["id"]

            token = await _pair_different_hardware(client, requester)
            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            payload = _payload(
                pairing_token=token, state_token=edit.json()["state_token"], confirm_node_identity_change=True,
            )
            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json=payload)
            assert preview.status_code == 200, preview.text

            applied = await client.post(
                f"/api/streams/{stream_id}/camera-configuration/apply",
                json={**payload, "preview_token": "stale-preview-token-from-another-tab", "idempotency_key": "interrupted-apply-001", "restart_monitoring": False},
            )
            assert applied.status_code == 409, applied.text

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    with repository.session_factory() as session:
        source = session.get(CameraSourceModel, ids["source_id"])
        assert source.camera_node_identity_replaced_at is None
        assert source.camera_node_prior_node_id is None
    repository.close()


def test_doctor_warns_after_a_real_confirmed_replacement(tmp_path) -> None:
    """Wiring proof against the real database and Doctor's real gather
    step -- `_interpret_camera_node`'s branch logic itself is exhaustively
    covered in tests/test_doctor.py."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code")
    ids: dict = {}

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]
            ids["source_id"] = completion["source"]["id"]

            token = await _pair_different_hardware(client, requester)
            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            payload = _payload(
                pairing_token=token, state_token=edit.json()["state_token"],
                confirm_node_identity_change=True, replacement_reason="Camera housing replaced",
            )
            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json=payload)
            applied = await client.post(
                f"/api/streams/{stream_id}/camera-configuration/apply",
                json={**payload, "preview_token": preview.json()["preview_token"], "idempotency_key": "doctor-apply-001", "restart_monitoring": False},
            )
            assert applied.status_code == 200, applied.text

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    gathered = doctor._gather_camera_node(repository.engine)
    result = doctor._interpret_camera_node(gathered, now=datetime.now(UTC))
    assert result.status == doctor.DoctorStatus.WARN
    assert "replaced" in result.summary.lower()
    assert "Camera housing replaced" in (result.detail or "")
    repository.close()


def test_replacement_reason_is_optional_and_bounded(tmp_path) -> None:
    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code")

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]

            token = await _pair_different_hardware(client, requester)
            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            payload = _payload(
                pairing_token=token, state_token=edit.json()["state_token"],
                confirm_node_identity_change=True, replacement_reason="x" * 281,
            )
            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json=payload)
            assert preview.status_code == 422  # rejected before ever reaching repository logic

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_ordinary_new_camera_onboarding_still_works(tmp_path) -> None:
    """Regression guard: the relaxed identity guard must not affect
    first-run pairing, which never has an existing node_id to compare
    against in the first place."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="only-code")

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="only-code")
            assert completion["source"]["id"]
            assert completion["stream"]["id"]

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()
