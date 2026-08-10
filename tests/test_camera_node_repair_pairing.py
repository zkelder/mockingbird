"""Camera Node repair/re-pair: a real native-Windows repro paired an existing
camera_node camera, explicitly revoked it through the UI, and then could not
repair it -- "Pair or repair Node" answered "The Camera Node pairing code was
rejected." twice against a still-valid, still-unconsumed one-time code from
the Node's own log.

Root cause was two compounding defects, neither specific to that one code or
camera:

- `CameraNodeClient.pair()` collapsed the Node's 401 ("this code is simply
  wrong") and 409 ("this code was already consumed by an earlier accepted
  pairing") into the identical `pairing_rejected` error and the identical
  "The Camera Node pairing code was rejected." text. A 409 is not a verdict
  about the code at all -- it means *some* `pair()` call already succeeded
  with it, which is a local repair-state question ("did my last attempt
  actually work?"), never grounds to conclude the code itself is bad.
- Unlike first-run setup (`CameraSetupPage.tsx`, `GET
  /api/camera-nodes/pending-setup`), the repair page
  (`CameraConfigurationPage.tsx`) had no way to discover or resume a repair
  pairing that already succeeded server-side but was never saved (a reload,
  a closed tab, or simply not reaching Save yet). That already-consumed
  one-time code becomes permanently unusable, and the only UI-visible
  recourse -- re-entering the same code -- is the 409 above, shown as an
  indistinguishable "was rejected".

These tests exercise the same public `/api/camera-nodes/*` and
`/api/streams/{id}/camera-configuration/*` routes the browser uses,
mirroring tests/test_camera_node_pairing_persistence.py's conventions for
the first-run flow (which this file deliberately does not duplicate
coverage of).
"""

from __future__ import annotations

import asyncio
import json

import httpx
import pytest
from sqlalchemy import func, select

from mockingbird.api import main as api_main
from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers.camera_node import CameraNodeClient
from mockingbird.storage.models import CameraNodePendingSetupModel, ZoneModel


NEVER_ECHO_CREDENTIAL_1 = "never-echo-first-run-credential"
NEVER_ECHO_CREDENTIAL_2 = "never-echo-repaired-credential"
BASE_ADDRESS = "http://192.168.1.112:8787"


class _StatefulNodeRequester:
    """A fixed-response fake Node (see tests/test_camera_node.py) whose
    `/pair` endpoint additionally mirrors mockingbird_node.app._PairingState's
    real one-time-code semantics: one correct code, consumable exactly once,
    a wrong code answered 401 *without* consuming it, a re-used code answered
    409 -- so repair's malformed/expired/already-used/genuinely-wrong-code
    paths can each be reproduced precisely without a live Node process."""

    def __init__(self, *, correct_code: str, credential: str = NEVER_ECHO_CREDENTIAL_1, node_id: str = "node-feeder") -> None:
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.timings: list[object] = []
        self.correct_code = correct_code
        self.credential = credential
        self.node_id = node_id
        self.consumed = False
        # Flip False to simulate the Node genuinely rejecting an already-
        # accepted credential on a later authenticated call.
        self.authenticated = True
        self.pair_status_override: int | None = None

    def request(self, *, method, url, headers, body, max_bytes, timing):
        self.requests.append((method, url, headers))
        self.timings.append(timing)
        if url.endswith("/health"):
            return 200, {"Content-Type": "application/json"}, json.dumps(
                {"node_id": self.node_id, "display_name": "Feeder Node", "api_version": "v1"}
            ).encode()
        if url.endswith("/pair") and method == "POST":
            if self.pair_status_override is not None:
                return self.pair_status_override, {"Content-Type": "application/json"}, b'{"detail":"forced"}'
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


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


def _repository(tmp_path, *, name: str = "camera-node-repair.sqlite3") -> ProductRepository:
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
    """Exactly what CameraConfigurationPage.tsx's pairNodeForRepair() sends:
    no renews_pairing_token -- that field is a first-run "needs_renewal"
    resume concept a repair of an already-completed camera never has."""

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


async def _revoke_stream_pairing(client: httpx.AsyncClient, stream_id: str) -> None:
    revoked = await client.post("/api/camera-nodes/pair/revoke", json={"stream_id": stream_id})
    assert revoked.status_code == 204, revoked.text


def _repair_payload(*, pairing_token: str, state_token: str, camera_id: str = "opaque-camera-1") -> dict:
    """Exactly what CameraConfigurationPage.tsx's configurationPayload()
    sends for a camera_node repair: config carries only the opaque
    advertised camera id, never the credential, which travels only as
    node_pairing_token."""

    return {
        "provider_key": "camera_node",
        "config": {"node_camera_id": camera_id},
        "secret_actions": {},
        "node_pairing_token": pairing_token,
        "source_name": None,
        "stream_name": None,
        "expected_state_token": state_token,
    }


def test_repair_pairing_after_explicit_revoke_succeeds_and_preserves_identity(tmp_path) -> None:
    """The real repro this fix targets, driven end to end: first-run
    pair+complete, an explicit "Revoke current pairing", then repair with a
    fresh code -- the Save step preserves the existing Source/Stream/Zone
    and replaces only the pairing credential (task point 6)."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code")
    result: dict = {}

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]
            source_id = completion["source"]["id"]
            result["stream_id"] = stream_id
            result["source_id"] = source_id

            await _revoke_stream_pairing(client, stream_id)

            edit_before = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            assert edit_before.status_code == 200

            # "Pi was restarted with pairing state cleared": a fresh,
            # still-valid, not-yet-consumed one-time code, exactly like the
            # real repro's e55-yalpuCkcEfsj2DzOHclU.
            requester.correct_code = "repair-code"
            requester.consumed = False
            requester.credential = NEVER_ECHO_CREDENTIAL_2

            repaired = await _pair(client, code="repair-code")
            assert repaired.status_code == 200, repaired.text
            repair_token = repaired.json()["pairing_token"]

            payload = _repair_payload(
                pairing_token=repair_token,
                state_token=edit_before.json()["state_token"],
            )
            preview = await client.post(
                f"/api/streams/{stream_id}/camera-configuration/preview", json=payload
            )
            assert preview.status_code == 200, preview.text
            assert preview.json()["validation"]["can_apply"] is True
            assert NEVER_ECHO_CREDENTIAL_2 not in preview.text

            applied = await client.post(
                f"/api/streams/{stream_id}/camera-configuration/apply",
                json={
                    **payload,
                    "preview_token": preview.json()["preview_token"],
                    "idempotency_key": "repair-apply-001",
                    "restart_monitoring": False,
                },
            )
            assert applied.status_code == 200, applied.text
            assert NEVER_ECHO_CREDENTIAL_2 not in applied.text
            configuration = applied.json()["configuration"]
            assert configuration["source_id"] == source_id
            assert configuration["stream_id"] == stream_id

            # Nothing about finishing the repair requires touching the Node
            # a second time -- the credential the browser already paired is
            # what got saved.
            pair_calls = sum(1 for method, url, _ in requester.requests if method == "POST" and url.endswith("/pair"))
            assert pair_calls == 2  # first-run + repair, never a third

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None

    with repository.session_factory() as session:
        # The redundant pending row from the repair pairing is cleaned up in
        # the same transaction as Save, same as first-run's own `complete`.
        assert (session.scalar(select(func.count(CameraNodePendingSetupModel.token))) or 0) == 0
        zones = session.query(ZoneModel).filter_by(stream_id=result["stream_id"]).all()
        assert [zone.name for zone in zones] == ["Feeder"]
    repository.close()


def test_repair_pairing_rejects_a_genuinely_wrong_code_as_a_node_rejection(tmp_path) -> None:
    """A code that simply does not match what the Node expects is a genuine
    Node rejection -- distinct from "already used" (below) and from
    "malformed" (below that)."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="correct-code")

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            response = await _pair(client, code="a-completely-wrong-code")
            assert response.status_code == 409
            assert response.json()["detail"] == "The Camera Node pairing code was rejected."
            # A genuine wrong-code guess must never consume the real code.
            resumed = await _pair(client, code="correct-code")
            assert resumed.status_code == 200, resumed.text

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_repair_pairing_reusing_an_already_consumed_code_is_a_distinct_local_state_message(tmp_path) -> None:
    """The exact bug: resubmitting a code that already succeeded once must
    not be shown as indistinguishable from a genuinely wrong code -- this was
    "The Camera Node pairing code was rejected." for both, twice, in the real
    repro. Once a pairing has genuinely succeeded, the Node's own one-time-
    code state (see mockingbird_node.app._PairingState.pair) no longer even
    distinguishes a repeat of the right code from a guess at a different one
    -- both mean "I already have a credential" (409) -- so this is also the
    accurate outcome for a wrong-guess *after* an earlier success, not only
    for an exact repeat."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="only-once-code")

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            first = await _pair(client, code="only-once-code")
            assert first.status_code == 200, first.text

            same_code_again = await _pair(client, code="only-once-code")
            assert same_code_again.status_code == 409
            assert same_code_again.json()["detail"] == (
                "This one-time code was already used for a pairing attempt. If a "
                "repair or setup already completed, refresh to resume it before "
                "requesting a new code from the Camera Node."
            )

            different_code_after_success = await _pair(client, code="never-the-right-code")
            assert different_code_after_success.status_code == 409
            assert different_code_after_success.json()["detail"] == same_code_again.json()["detail"]

            # The genuinely-wrong-code message (a fresh, never-yet-paired
            # Node -- see test_repair_pairing_rejects_a_genuinely_wrong_code_
            # as_a_node_rejection) is never this text.
            assert same_code_again.json()["detail"] != "The Camera Node pairing code was rejected."

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_repair_pairing_malformed_code_never_reaches_the_node(tmp_path) -> None:
    """A whitespace-only code passes the request schema's min_length check
    but is empty once trimmed -- caught locally, before any /pair request,
    and reported as a malformed request rather than a Node verdict."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="correct-code")

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            response = await _pair(client, code="          ")
            assert response.status_code == 400
            assert "enter" in response.json()["detail"].lower()

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    assert not any(url.endswith("/pair") and method == "POST" for method, url, _ in requester.requests)


def test_repair_pairing_expired_and_rate_limited_codes_are_distinct_from_rejection(tmp_path) -> None:
    """Regression coverage: repair had zero coverage of these two codes
    before this fix even though the mapping already existed."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="correct-code")

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            requester.pair_status_override = 410
            expired = await _pair(client, code="anything")
            assert expired.status_code == 409
            assert "expired" in expired.json()["detail"].lower()

            requester.pair_status_override = 429
            limited = await _pair(client, code="anything")
            assert limited.status_code == 409
            assert "limited" in limited.json()["detail"].lower()

            assert expired.json()["detail"] != limited.json()["detail"]

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_repair_resumes_a_successful_unsaved_pairing_instead_of_orphaning_it(tmp_path) -> None:
    """The structural fix: a repair pairing that already succeeded but was
    never saved (a reload, a closed tab, simply not reaching Save yet) must
    stay discoverable and resumable, not vanish behind an already-consumed
    one-time code with no local memory of the success."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code")

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]
            await _revoke_stream_pairing(client, stream_id)

            # Nothing pending yet -- an honest 404, not an empty success.
            none_yet = await client.get(f"/api/streams/{stream_id}/camera-configuration/pending-pairing")
            assert none_yet.status_code == 404

            requester.correct_code = "repair-code"
            requester.consumed = False
            paired = await _pair(client, code="repair-code")
            assert paired.status_code == 200, paired.text
            paired_token = paired.json()["pairing_token"]

            # Simulate "closed the tab before Save": a brand-new, stateless
            # GET with nothing remembered client-side except which Stream is
            # being repaired -- exactly what a reloaded page can still ask.
            resumed = await client.get(f"/api/streams/{stream_id}/camera-configuration/pending-pairing")
            assert resumed.status_code == 200
            body = resumed.json()
            assert body["pairing_token"] == paired_token
            assert body["status"] == "active"
            assert any(camera["camera_id"] == "opaque-camera-1" for camera in body["cameras"])
            assert NEVER_ECHO_CREDENTIAL_1 not in resumed.text

            # The resumed token still finishes the repair normally.
            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            payload = _repair_payload(pairing_token=paired_token, state_token=edit.json()["state_token"])
            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json=payload)
            assert preview.status_code == 200, preview.text
            applied = await client.post(
                f"/api/streams/{stream_id}/camera-configuration/apply",
                json={**payload, "preview_token": preview.json()["preview_token"], "idempotency_key": "resume-apply-001", "restart_monitoring": False},
            )
            assert applied.status_code == 200, applied.text

            # Never re-submitted the one-time code a second time to get here.
            assert sum(1 for method, url, _ in requester.requests if method == "POST" and url.endswith("/pair")) == 2

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_repair_pending_pairing_never_surfaces_an_unrelated_nodes_pairing(tmp_path) -> None:
    """Safety scoping: an in-progress *first-run* "Add Camera" pairing for a
    different Node must never be offered as this Stream's repair resume."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code")

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]

            # An unrelated, still-pending first-run pairing for some other
            # (different node_id) Camera Node -- e.g. the user separately
            # started "Add Camera" for a second, different Pi.
            requester.node_id = "node-a-totally-different-pi"
            requester.correct_code = "other-node-code"
            requester.consumed = False
            other = await _pair(client, code="other-node-code")
            assert other.status_code == 200, other.text

            unrelated = await client.get(f"/api/streams/{stream_id}/camera-configuration/pending-pairing")
            assert unrelated.status_code == 404

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()


def test_cancel_pairing_attempt_revokes_at_the_node_and_stops_offering_resume(tmp_path) -> None:
    """The explicit "Cancel this pairing attempt" recovery action: a user who
    does not want to keep a just-paired-but-unsaved credential can abandon
    it cleanly, using the same authenticated Node revoke call first-run's
    "Forget this Camera Node" already used."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code")

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]
            await _revoke_stream_pairing(client, stream_id)

            requester.correct_code = "repair-code"
            requester.consumed = False
            paired = await _pair(client, code="repair-code")
            token = paired.json()["pairing_token"]

            canceled = await client.post(
                "/api/camera-nodes/pending-setup/revoke", json={"pairing_token": token}
            )
            assert canceled.status_code == 204

            after = await client.get(f"/api/streams/{stream_id}/camera-configuration/pending-pairing")
            assert after.status_code == 404

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()

    assert any(url.endswith("/pair/revoke") for _, url, _ in requester.requests)


def test_repair_apply_verifies_the_live_camera_like_first_run_complete_does(tmp_path) -> None:
    """Parity with first-run: `/api/camera-setup/complete` verifies the paired
    credential against the Node before saving it (`verify_camera=True`); a
    repair's Save step must do the same instead of silently persisting a
    credential the Node has already stopped accepting."""

    repository = _repository(tmp_path)
    requester = _StatefulNodeRequester(correct_code="first-run-code")

    async def scenario() -> None:
        async with _client_for(repository, requester) as client:
            completion = await _first_run_complete(client, code="first-run-code")
            stream_id = completion["stream"]["id"]
            await _revoke_stream_pairing(client, stream_id)

            requester.correct_code = "repair-code"
            requester.consumed = False
            paired = await _pair(client, code="repair-code")
            token = paired.json()["pairing_token"]

            # The Node accepted the pairing call itself, but has since
            # stopped trusting the resulting credential on authenticated
            # calls -- a genuine, live rejection Save must actually notice.
            requester.authenticated = False

            edit = await client.get(f"/api/streams/{stream_id}/camera-configuration")
            payload = _repair_payload(pairing_token=token, state_token=edit.json()["state_token"])
            preview = await client.post(f"/api/streams/{stream_id}/camera-configuration/preview", json=payload)
            assert preview.status_code == 200  # preview never live-checks, like first-run's validate

            applied = await client.post(
                f"/api/streams/{stream_id}/camera-configuration/apply",
                json={**payload, "preview_token": preview.json()["preview_token"], "idempotency_key": "verify-apply-001", "restart_monitoring": False},
            )
            assert applied.status_code == 400
            assert "no longer accepted" in applied.json()["detail"].lower()

            # The now-known-bad pending pairing is marked for renewal, not
            # left indistinguishable from a healthy resumable one.
            resumed = await client.get(f"/api/streams/{stream_id}/camera-configuration/pending-pairing")
            assert resumed.status_code == 200
            assert resumed.json()["status"] == "needs_renewal"

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()
