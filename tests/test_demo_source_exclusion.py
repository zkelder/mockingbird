"""Pre-Release Trust & Correctness Correction v1 (UI-01), extended by
Native-Windows & Packaging Acceptance v1.

A fresh installation seeds a demo Source (`SourceKind.demo`,
`source-backyard-demo`) with two fabricated example Visits so the product
is not empty before a user adds a real camera (see
`mockingbird.api.demo_data`). A 2026-09-21 baseline audit found Dashboard
"Recent activity" and Bird Log rendered this fabricated content as real,
unlabeled, Reviewed wildlife history -- confirmed live with screenshots.
Roughly eight sibling call sites already excluded `SourceKind.demo`
activity from real product history; these two were the exception.

A real native-Windows acceptance run of the packaged artifact (Native-
Windows & Packaging Acceptance v1) found the identical gap one layer
over: the Review Queue itself (`GET /api/review-queue`) -- and every
Dashboard headline field derived from it or from a sibling raw count
query (`needs_review_visit_count`, the per-stream `needs_review_counts`,
`actionable_animal_visit_count`, `legacy_activity_count`) -- still showed
the seeded demo Visit as a genuine item needing review on a brand-new
install. Fixed at `GET /api/review-queue` and in `dashboard_summary`'s own
`product_review_items` derivation by filtering on `_review_queue_product_
context`'s already-computed `is_demo_source`; the two raw COUNT queries
(`needs_review_visit_count`, per-stream `needs_review_counts`) got the
same join+`_real_source_condition()` shape their sibling `needs_rows`
query already used.

That first pass left `_review_queue_product_context` computing
`is_demo_source` from `source.kind == demo OR provider_key == "demo"` --
an OR that, unlike `_real_source_condition()`'s own precedent, could never
stop being true once `kind == "demo"`, no matter what real provider a
Source later gained. `_real_source_condition`'s own docstring names exactly
this scenario (Guided Camera Editing repurposing the seeded demo Source
into a real `camera_node` Source, `kind` staying `"demo"` forever) as the
reason `kind` must never be the deciding signal once a real provider row
exists. Corrected to mirror `_real_source_condition()` exactly: a real
provider row's own `provider_key` wins when present, `kind` decides only
as the fallback for a Source with no provider row yet -- see
`test_a_repurposed_demo_source_no_longer_counts_as_demo`, below, for the
dedicated regression test.

These tests deliberately construct a `ProductRepository` against a brand
new, empty SQLite database and change nothing else -- `seed_if_empty()`
(called unconditionally from `ProductRepository.__init__`) seeds the demo
Source/Visits exactly as a genuine first launch would, so this is the
fresh-install scenario itself, not a simulation of it.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from mockingbird.api import demo_data
from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import LegacyAuthenticatedTestClient, de_demo_seeded_source

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def fresh_repository(tmp_path: Path) -> ProductRepository:
    """A brand-new database -- `seed_if_empty()` seeds the demo Source and
    its two fabricated Visits, and nothing else is added."""

    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    yield repository
    repository.close()


@pytest.fixture
async def client(fresh_repository: ProductRepository):
    configure_repository(fresh_repository)
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client
    configure_repository(None)


def test_demo_data_is_genuinely_seeded_by_a_fresh_repository(fresh_repository: ProductRepository) -> None:
    """Sanity check on the fixture itself: if this ever stops being true
    (demo seeding removed or changed), the rest of this file's tests would
    pass for the wrong reason (nothing to exclude) rather than proving the
    exclusion actually works -- catch that here, explicitly and first."""

    with fresh_repository.session_factory() as session:
        from mockingbird.storage.models import CameraSourceModel, VisitModel

        assert session.get(CameraSourceModel, demo_data.SOURCE_ID) is not None
        assert session.get(VisitModel, "visit-bird-feeder-001") is not None
        assert session.get(VisitModel, "visit-squirrel-ground-001") is not None


def test_fresh_install_dashboard_recent_activity_is_honestly_empty(
    fresh_repository: ProductRepository,
) -> None:
    summary = fresh_repository.dashboard_summary()

    assert summary.recent_activity == []
    assert summary.headline.real_stream_count == 0


async def test_dashboard_summary_api_excludes_demo_visits_from_recent_activity(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()

    recent_ids = {visit["id"] for visit in payload["recent_activity"]}
    assert "visit-bird-feeder-001" not in recent_ids
    assert "visit-squirrel-ground-001" not in recent_ids
    assert payload["recent_activity"] == []


async def test_bird_log_journal_overview_excludes_the_demo_squirrel(
    client: httpx.AsyncClient,
) -> None:
    """The demo squirrel Visit (`visit-squirrel-ground-001`) is seeded
    already reviewed as `"squirrel"` (see `demo_data.py`) -- exactly the
    shape ("Reviewed" wildlife history) that made this defect look
    convincing rather than obviously fake."""

    response = await client.get("/api/bird-log/journal")
    assert response.status_code == 200
    payload = response.json()

    assert payload["labels"] == []

    squirrel_response = await client.get("/api/bird-log/journal/squirrel")
    assert squirrel_response.status_code == 200
    squirrel_payload = squirrel_response.json()
    assert squirrel_payload["observation_count"] == 0
    observation_ids = {item["visit_id"] for item in squirrel_payload["gallery"]["observations"]}
    assert "visit-squirrel-ground-001" not in observation_ids


async def test_a_real_visit_on_a_non_demo_source_still_appears(
    client: httpx.AsyncClient, fresh_repository: ProductRepository,
) -> None:
    """The fix must exclude only the demo Source's own activity, never
    real activity generally -- a real, non-demo Visit must still show up
    on both surfaces exactly as before."""

    from datetime import UTC, datetime, timedelta

    from mockingbird.storage.models import (
        CameraSourceModel,
        EventModel,
        StreamModel,
        VisitModel,
        ZoneModel,
    )

    started_at = datetime.now(UTC) - timedelta(minutes=5)
    with fresh_repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id="source-real-camera", name="Real backyard camera",
                    kind="manual_upload", status="connected", description="A genuine, non-demo source.",
                )
            )
            session.add(
                StreamModel(
                    id="stream-real-camera", source_id="source-real-camera",
                    name="Real backyard stream", description="A genuine, non-demo stream.", is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id="zone-real-camera", stream_id="stream-real-camera", name="Feeder", zone_type="feeder",
                    polygon_json="[]", is_active=True, monitoring_policy_json=None,
                )
            )
            session.add(
                EventModel(
                    id="event-real-visit", stream_id="stream-real-camera", title="Real activity",
                    event_type="observation_engine_candidate", started_at=started_at,
                    ended_at=started_at + timedelta(seconds=5), primary_zone_id="zone-real-camera",
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id="visit-real-001", event_id="event-real-visit", subject_label="bird",
                    species_guess="northern_cardinal", confidence=None, reviewed_label=None,
                    review_status="needs_review", zone_id="zone-real-camera", is_superseded=False,
                )
            )

    response = await client.get("/api/dashboard/summary")
    assert response.status_code == 200
    recent_ids = [visit["id"] for visit in response.json()["recent_activity"]]
    assert recent_ids == ["visit-real-001"]


def test_fresh_install_review_queue_is_honestly_empty(
    fresh_repository: ProductRepository,
) -> None:
    """Found live on a real native-Windows install: the seeded demo
    Source's own `visit-bird-feeder-001` (needs_review, a fabricated
    `northern_cardinal` suggestion) appeared as a genuine Review Queue
    item on a brand-new install with zero real cameras configured.

    The repository method itself deliberately still returns the item,
    correctly `is_demo_source`-flagged -- `test_review_queue_product_mode.py`
    already depends on that contract for internal callers. The exclusion
    that actually matters to a user belongs at the product-facing HTTP
    boundary (see `test_review_queue_api_excludes_demo_visits`, below)."""

    items = fresh_repository.review_queue_items()
    assert [item.is_demo_source for item in items] == [True]


async def test_review_queue_api_excludes_demo_visits(client: httpx.AsyncClient) -> None:
    response = await client.get("/api/review-queue")
    assert response.status_code == 200
    assert response.json() == []


async def test_dashboard_needs_review_counts_exclude_demo_visits(
    client: httpx.AsyncClient,
) -> None:
    """The raw `needs_review_visit_count`/per-stream `needs_review_counts`
    COUNT queries are siblings of the already-demo-excluding `needs_rows`
    query in the same function -- this proves they now match it."""

    response = await client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()

    assert payload["headline"]["needs_review_visit_count"] == 0
    assert payload["headline"]["actionable_animal_visit_count"] == 0
    assert payload["headline"]["legacy_activity_count"] == 0
    for stream in payload["streams"]:
        assert stream["needs_review_visit_count"] == 0


async def test_a_real_visit_on_a_non_demo_source_still_appears_in_review_queue(
    client: httpx.AsyncClient, fresh_repository: ProductRepository,
) -> None:
    """The fix must exclude only the demo Source's own activity -- a real,
    non-demo, needs-review Visit must still reach the Review Queue and the
    Dashboard's derived counts exactly as before."""

    from datetime import UTC, datetime, timedelta

    from mockingbird.storage.models import (
        CameraSourceModel,
        EventModel,
        StreamModel,
        VisitModel,
        ZoneModel,
    )

    started_at = datetime.now(UTC) - timedelta(minutes=5)
    with fresh_repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id="source-real-camera-2", name="Real backyard camera 2",
                    kind="manual_upload", status="connected", description="A genuine, non-demo source.",
                )
            )
            session.add(
                StreamModel(
                    id="stream-real-camera-2", source_id="source-real-camera-2",
                    name="Real backyard stream 2", description="A genuine, non-demo stream.", is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id="zone-real-camera-2", stream_id="stream-real-camera-2", name="Feeder", zone_type="feeder",
                    polygon_json="[]", is_active=True, monitoring_policy_json=None,
                )
            )
            session.add(
                EventModel(
                    id="event-real-visit-2", stream_id="stream-real-camera-2", title="Real activity",
                    event_type="observation_engine_candidate", started_at=started_at,
                    ended_at=started_at + timedelta(seconds=5), primary_zone_id="zone-real-camera-2",
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id="visit-real-002", event_id="event-real-visit-2", subject_label="bird",
                    species_guess="northern_cardinal", confidence=None, reviewed_label=None,
                    review_status="needs_review", zone_id="zone-real-camera-2", is_superseded=False,
                )
            )

    response = await client.get("/api/review-queue")
    assert response.status_code == 200
    item_ids = [item["id"] for item in response.json()]
    assert item_ids == ["review-queue-visit-real-002"]

    dashboard_response = await client.get("/api/dashboard/summary")
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["headline"]["needs_review_visit_count"] == 1


async def test_a_repurposed_demo_source_no_longer_counts_as_demo(
    client: httpx.AsyncClient, fresh_repository: ProductRepository,
) -> None:
    """`_real_source_condition`'s own docstring names this exact scenario:
    Guided Camera Editing repurposing the seeded demo Source into a real
    `camera_node` Source keeps `kind="demo"` forever, so only the Source's
    *effective* provider (a real `SourceProviderConfigurationModel` row)
    may decide "is this demo" -- `kind` is the fallback for a Source with
    no such row, never the deciding signal once one exists. An earlier
    version of `_review_queue_product_context` still checked `kind` even
    when a real provider row existed, so a repurposed demo Source's own
    pre-existing seeded Visit could never stop reading as demo/
    `legacy_activity`. `de_demo_seeded_source` performs the identical
    real-product repurposing this test proves: inserting a real,
    non-"demo" `SourceProviderConfigurationModel` row for the seeded
    demo Source, changing nothing else."""

    de_demo_seeded_source(fresh_repository)

    response = await client.get("/api/review-queue")
    assert response.status_code == 200
    item_ids = {item["id"] for item in response.json()}
    assert "review-queue-visit-bird-feeder-001" in item_ids

    dashboard_response = await client.get("/api/dashboard/summary")
    assert dashboard_response.status_code == 200
    assert dashboard_response.json()["headline"]["needs_review_visit_count"] == 1
