"""Clean-install acceptance: the whole first-hour golden path, driven
through the real HTTP API against a genuinely fresh, empty database (First-
Hour Onboarding + Whole-Product Observability Closure v1, "A9").

Confirmed by this milestone's own investigation as a real, if narrow, gap:
strong disjoint test coverage already existed for onboarding-wizard state,
Camera Node pairing persistence, migrations, and Today's report states
individually -- but no single test chained empty DB -> migrate -> configure
a source -> validate -> monitor -> first report through the actual FastAPI
HTTP layer end to end. This is that chain.

Reuses, rather than reinvents, the established fake-Camera-Node-requester
convention from test_camera_node_pairing_persistence.py (`_FakeNodeRequester`,
duplicated per that file's own documented "keep each test file self-
contained" convention) -- a deterministic fake/reference provider, per this
milestone's own instruction: "Do not pretend a fake provider validates Pi
hardware. It validates the product flow."
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

from mockingbird.api import main as api_main
from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers.camera_node import CameraNodeClient
from tests.conftest import LegacyAuthenticatedTestClient

NEVER_ECHO_CREDENTIAL = "never-echo-node-credential"


class _FakeNodeRequester:
    """See test_camera_node_pairing_persistence.py's identical fixture --
    duplicated per this repository's own established "keep each test file
    self-contained" convention."""

    def __init__(self) -> None:
        self.requests: list[tuple[str, str, dict[str, str]]] = []

    def request(self, *, method, url, headers, body, max_bytes, timing):
        self.requests.append((method, url, headers))
        if url.endswith("/health"):
            return (
                200,
                {"Content-Type": "application/json"},
                json.dumps({"node_id": "node-test", "display_name": "Test node", "api_version": "v1"}).encode(),
            )
        if url.endswith("/pair"):
            assert body and b"pairing_code" in body
            return (
                200,
                {"Content-Type": "application/json"},
                json.dumps(
                    {
                        "node_id": "node-test",
                        "display_name": "Test node",
                        "api_version": "v1",
                        "credential": NEVER_ECHO_CREDENTIAL,
                        "cameras": [
                            {
                                "camera_id": "opaque-camera-1",
                                "display_name": "Feeder view",
                                "status": "available",
                                "snapshot_supported": True,
                            }
                        ],
                    }
                ).encode(),
            )
        if url.endswith("/capabilities"):
            return 200, {"Content-Type": "application/json"}, json.dumps({"recommended_snapshot_timeout_seconds": 8.0}).encode()
        if url.endswith("/cameras"):
            return (
                200,
                {"Content-Type": "application/json"},
                json.dumps(
                    {
                        "items": [
                            {
                                "camera_id": "opaque-camera-1",
                                "display_name": "Feeder view",
                                "status": "available",
                                "snapshot_supported": True,
                                "provider_type": "v4l2",
                            }
                        ]
                    }
                ).encode(),
            )
        if "/snapshot" in url:
            return 200, {"Content-Type": "image/jpeg"}, b"\xff\xd8fake\xff\xd9"
        return 404, {"Content-Type": "application/json"}, b"{}"


def _fresh_repository(tmp_path: Path) -> ProductRepository:
    """A genuinely empty database file -- the real `initialize_database`
    migration-from-zero path runs for real here, not a pre-seeded fixture
    someone rewound partway (see test_persistence.py's own convention)."""

    return ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'clean-install.sqlite3'}",
        media_root=tmp_path / "media",
    )


def _client_for(repository: ProductRepository, requester: _FakeNodeRequester) -> httpx.AsyncClient:
    api_main._camera_node_client = CameraNodeClient(requester=requester)
    configure_repository(repository)
    transport = httpx.ASGITransport(app=app)
    return LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver")


def test_clean_install_reaches_a_first_report_through_the_real_http_api(tmp_path: Path) -> None:
    """clean install -> migrations from zero -> initial API health ->
    configure one acquisition source (Camera Node) -> validate ->
    monitoring/start -> first report API -> frontend route reachable
    (proxy: the API surface the frontend route renders from)."""

    repository = _fresh_repository(tmp_path)

    async def scenario() -> None:
        async with _client_for(repository, _FakeNodeRequester()) as client:
            # 1. Initial API health -- the process is up and the freshly-
            # migrated database is reachable, before any product action.
            health = await client.get("/health")
            assert health.status_code == 200

            instance = await client.get("/api/product/instance")
            assert instance.status_code == 200
            assert instance.json()["app_version"]

            setup_state = await client.get("/api/setup/state")
            assert setup_state.status_code == 200
            assert setup_state.json()["completed"] is False  # a genuinely fresh DB never skips onboarding

            # 2. Configure one acquisition source: pair a Camera Node (the
            # documented golden path -- see "A4 golden path priority").
            paired = await client.post(
                "/api/camera-nodes/pair",
                json={"base_address": "http://127.0.0.1:8787", "pairing_code": "correct-one-time-code"},
            )
            assert paired.status_code == 200
            token = paired.json()["pairing_token"]

            # 3. Validate before completing -- exactly what the frontend
            # wizard does before enabling "Finish setup."
            validation = await client.post(
                "/api/camera-setup/validate",
                json={
                    "provider_key": "camera_node",
                    "config": {"node_camera_id": "opaque-camera-1"},
                    "node_pairing_token": token,
                },
            )
            assert validation.status_code == 200
            assert validation.json()["status"] == "configuration_valid"

            # 4. Complete setup -- atomically creates Source + Stream + Zone.
            completion = await client.post(
                "/api/camera-setup/complete",
                json={
                    "camera_name": "Backyard camera",
                    "stream_name": "Backyard camera view",
                    "provider_key": "camera_node",
                    "config": {"node_camera_id": "opaque-camera-1"},
                    "node_pairing_token": token,
                    "zones": [
                        {
                            "name": "Feeder",
                            "zone_type": "feeder",
                            "polygon": [
                                {"x": 0.2, "y": 0.2},
                                {"x": 0.8, "y": 0.2},
                                {"x": 0.8, "y": 0.8},
                                {"x": 0.2, "y": 0.8},
                            ],
                        }
                    ],
                    "enable_monitoring": False,
                    "idempotency_key": "clean-install-acceptance-key",
                },
            )
            assert completion.status_code == 200
            stream_id = completion.json()["stream"]["id"]

            # 5. Monitoring/start-or-equivalent. A real detector model bundle
            # is not installed in this hermetic test environment -- per this
            # milestone's own instruction, that's honestly reported, not
            # faked into "observing." The contract under test is that the
            # attempt is reachable and returns a real, structured status
            # (never a 500/crash) -- proving the product flow is wired, not
            # that GPU/model inference succeeded (see "A9 clean-install
            # test").
            start = await client.post(f"/api/streams/{stream_id}/observation/start")
            assert start.status_code == 200
            assert start.json()["state"] in {"observing", "starting", "needs_attention"}

            # 6. First report API -- Today/Digest must render a real,
            # honest early state for a source configured only seconds ago,
            # never an error.
            dashboard = await client.get("/api/dashboard/summary")
            assert dashboard.status_code == 200
            dashboard_body = dashboard.json()
            assert dashboard_body["headline"]["real_stream_count"] >= 1

            now = datetime.now(UTC)
            report = await client.post(
                "/api/analytics/place-activity-report",
                json={"start_at": (now - timedelta(days=1)).isoformat(), "end_at": now.isoformat()},
            )
            assert report.status_code == 200

            # 7. Frontend route reachable: the same-origin static app shell
            # this exact API backs (web_app.py) answers for the root route
            # a real browser opens -- proxy for "frontend route reachable"
            # per this milestone's own instruction, since this test suite
            # cannot drive a real browser.
            root = await client.get("/")
            assert root.status_code == 200

    try:
        asyncio.run(scenario())
    finally:
        configure_repository(None)
        api_main._camera_node_client = None
        repository.close()
