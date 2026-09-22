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

Review Queue Count Truth Consistency v1 extends this file. Native-Windows
& Packaging Acceptance v1 fixed `GET /api/review-queue` and `dashboard_
summary`, but disclosed roughly a dozen sibling `review_queue_count`
response fields (Manual Import, Folder Import, Model Adapters, Detection
Proposals, and the core review/correction flow itself) still computing an
unfiltered `len(_review_queue_items(...))`, surfaced to users as "N needs
review" pills/toasts. `ProductRepository._visible_review_queue_items`/
`_visible_review_queue_count` (product_repository.py, immediately after
`_review_queue_items` itself) is the one shared seam introduced to close
all of them at once instead of reproducing the filter ad hoc; the tests
below prove it directly and at each distinct response shape it now backs.

Analytics & Local Data Truth Consistency v1 extends this file again. Review
Queue Count Truth Consistency v1's own report disclosed a larger, separate
family it deliberately left unfixed: `AnalyticsSummary.needs_review_count`
(and its siblings `event_count`/`visit_count`/`species_counts`/
`zone_activity_counts`, all computed together in `_analytics_summary`) and
`YardMapActivitySummary.needs_review_count` (a different computation
entirely, in `_yard_map_activity_summary`) were both still demo-inclusive,
feeding `AnalyticsPage.tsx`, `LocalDataPage.tsx`, `DatasetCoveragePanel.tsx`
(via `_dataset_coverage_summary`), `DatasetQualityPanel.tsx` (via
`_dataset_quality_summary`), and `YardMapPage.tsx` -- every one framed to
the user as their own real reviewed/observed wildlife history, never as
demo/sample content. The new module-level `_real_stream_ids(session)`
helper (product_repository.py, immediately after `_real_source_condition`
itself) is the one shared seam these four Python-side aggregations now
filter through -- the same canonical `_real_source_condition()` contract
`_visible_review_queue_count` already established for the Review Queue
family, reused rather than re-derived. `LocalDataStatus`'s own raw
`_count(session, Model)` storage-inventory fields (`source_count`/
`stream_count`/`zone_count`/`review_label_count`/`dataset_export_count`/
etc.) are deliberately left demo-inclusive: `LocalDataPage.tsx` frames
them as "local source records"/"local import references" -- local-storage
diagnostics, not ecosystem history -- already honestly disclosed via
`seed_data_present`, exactly matching this repository's own established
`AdapterEvaluationSummary.unreviewed_count` precedent for a legitimate
non-"needs review" metric. See this milestone's own closure report for
the complete field-by-field contract.
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


def _add_real_stream_and_zone(
    repository: ProductRepository,
    *,
    suffix: str = "1",
) -> tuple[str, str]:
    """A Stream on a real (non-demo) Source -- this file's own equivalent
    of `test_fast_review.py`'s `add_real_stream`, needed for the same
    reason: proving a fix excludes only the seeded demo Source's own
    activity requires a genuine, non-demo Source/Stream/Zone to hold real
    activity against."""

    from mockingbird.storage.models import CameraSourceModel, StreamModel, ZoneModel

    source_id = f"source-truth-consistency-{suffix}"
    stream_id = f"stream-truth-consistency-{suffix}"
    zone_id = f"zone-truth-consistency-{suffix}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=source_id, name="Truth consistency real fixture camera",
                    kind="manual_upload", status="connected",
                    description="A genuine, non-demo source.",
                )
            )
            session.add(
                StreamModel(
                    id=stream_id, source_id=source_id,
                    name="Truth consistency real fixture stream",
                    description="A genuine, non-demo stream.", is_live=False,
                )
            )
            session.add(
                ZoneModel(
                    id=zone_id, stream_id=stream_id, name="Feeder", zone_type="feeder",
                    polygon_json="[]", is_active=True, monitoring_policy_json=None,
                )
            )
    return stream_id, zone_id


def _add_real_needs_review_visit(
    repository: ProductRepository,
    *,
    stream_id: str,
    zone_id: str,
    event_id: str,
    visit_id: str,
    species_guess: str = "northern_cardinal",
) -> None:
    """One genuine needs-review Visit on a real (non-demo) Stream -- mirrors
    `test_a_real_visit_on_a_non_demo_source_still_appears`'s own inline
    fixture, above, factored out because the tests below need it
    repeatedly rather than once."""

    from datetime import UTC, datetime, timedelta

    from mockingbird.storage.models import EventModel, VisitModel

    started_at = datetime.now(UTC) - timedelta(minutes=5)
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id, stream_id=stream_id, title="Real activity",
                    event_type="observation_engine_candidate", started_at=started_at,
                    ended_at=started_at + timedelta(seconds=5), primary_zone_id=zone_id,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id, event_id=event_id, subject_label="bird",
                    species_guess=species_guess, confidence=None, reviewed_label=None,
                    review_status="needs_review", zone_id=zone_id, is_superseded=False,
                )
            )


def test_visible_review_queue_count_is_zero_for_demo_only_queue(
    fresh_repository: ProductRepository,
) -> None:
    """The canonical helper behind every `review_queue_count` response
    field (`ProductRepository._visible_review_queue_count`) must read 0
    when the only needs-review activity belongs to the seeded demo Source
    -- not 1, the seeded demo Visit's own raw count."""

    with fresh_repository.session_factory() as session:
        assert fresh_repository._visible_review_queue_count(session) == 0


def test_visible_review_queue_count_counts_real_activity_alongside_demo(
    fresh_repository: ProductRepository,
) -> None:
    """Excludes the constant demo item while correctly counting real
    activity as it grows: proves the count is not hardcoded to 0 or 1, and
    that the seeded demo Visit never inflates it regardless of how much
    real activity exists alongside it."""

    stream_id, zone_id = _add_real_stream_and_zone(fresh_repository)
    _add_real_needs_review_visit(
        fresh_repository,
        stream_id=stream_id,
        zone_id=zone_id,
        event_id="event-truth-consistency-1",
        visit_id="visit-truth-consistency-1",
    )
    with fresh_repository.session_factory() as session:
        assert fresh_repository._visible_review_queue_count(session) == 1

    _add_real_needs_review_visit(
        fresh_repository,
        stream_id=stream_id,
        zone_id=zone_id,
        event_id="event-truth-consistency-2",
        visit_id="visit-truth-consistency-2",
    )
    with fresh_repository.session_factory() as session:
        assert fresh_repository._visible_review_queue_count(session) == 2


def test_repurposed_demo_source_counts_toward_visible_review_queue_count(
    fresh_repository: ProductRepository,
) -> None:
    """`de_demo_seeded_source` performs the real product repurposing
    mechanism (inserting a real `SourceProviderConfigurationModel` row) --
    once applied, the seeded demo Source's own pre-existing needs-review
    Visit must count as genuine work, exactly like `GET /api/review-queue`
    and `dashboard_summary` already established in
    `test_a_repurposed_demo_source_no_longer_counts_as_demo`, above."""

    de_demo_seeded_source(fresh_repository)
    with fresh_repository.session_factory() as session:
        assert fresh_repository._visible_review_queue_count(session) == 1


async def test_create_review_label_response_count_reflects_remaining_real_work(
    client: httpx.AsyncClient, fresh_repository: ProductRepository,
) -> None:
    """The core review/correction response (`POST /api/review-labels`) is
    the highest-priority surface this milestone must get right. Before
    this fix, correcting the one genuine needs-review Visit still reported
    `review_queue_count: 1` -- the seeded demo Visit's own count, presented
    as if it were still-outstanding real work. It must report 0."""

    stream_id, zone_id = _add_real_stream_and_zone(fresh_repository)
    _add_real_needs_review_visit(
        fresh_repository,
        stream_id=stream_id,
        zone_id=zone_id,
        event_id="event-correction-flow",
        visit_id="visit-correction-flow",
    )

    response = await client.post(
        "/api/review-labels",
        json={
            "review_origin": "human",
            "target_type": "visit",
            "target_id": "visit-correction-flow",
            "label": "northern_cardinal",
        },
    )
    assert response.status_code == 201
    assert response.json()["review_queue_count"] == 0


async def test_fast_review_undo_response_count_excludes_demo_activity(
    client: httpx.AsyncClient, fresh_repository: ProductRepository,
) -> None:
    """Fast Review's own undo response (`POST /api/review-queue/fast/undo`)
    is a sibling of the core correction response above and shared the
    identical pre-fix defect shape."""

    stream_id, zone_id = _add_real_stream_and_zone(fresh_repository)
    _add_real_needs_review_visit(
        fresh_repository,
        stream_id=stream_id,
        zone_id=zone_id,
        event_id="event-fast-undo",
        visit_id="visit-fast-undo",
    )
    items = (await client.get("/api/review-queue")).json()
    item = next(item for item in items if item["target_id"] == "visit-fast-undo")

    saved = await client.post(
        "/api/review-queue/fast/correct",
        json={
            "review_origin": "human",
            "target_type": "visit",
            "target_id": "visit-fast-undo",
            "label": "blue_jay",
            "review_session_id": "session-truth-consistency",
            "idempotency_key": "save-truth-consistency",
            "expected_state_token": item["review_state_token"],
        },
    )
    assert saved.status_code == 200
    body = saved.json()

    undone = await client.post(
        "/api/review-queue/fast/undo",
        json={
            "review_label_id": body["result"]["review_label"]["id"],
            "review_session_id": "session-truth-consistency",
            "idempotency_key": "undo-truth-consistency",
            "expected_state_token": body["undo_state_token"],
        },
    )
    assert undone.status_code == 200
    assert undone.json()["review_queue_count"] == 1


def test_media_import_response_count_excludes_demo_activity(
    fresh_repository: ProductRepository,
) -> None:
    """Manual Import's response (`MediaImportResult.review_queue_count`,
    the "N needs review" pill on `ManualImportPage.tsx`)."""

    stream_id, zone_id = _add_real_stream_and_zone(fresh_repository)
    result = fresh_repository.create_media_import(
        content=b"real import bytes",
        original_filename="real-bird.png",
        content_type="image/png",
        stream_id=stream_id,
        zone_id=zone_id,
    )
    assert result.review_queue_count == 1


def test_folder_import_response_count_excludes_demo_activity(
    fresh_repository: ProductRepository, tmp_path: Path,
) -> None:
    """Folder Import's response (`FolderImportResult.review_queue_count`,
    the "N needs review" pill on `FolderImportPage.tsx`)."""

    from mockingbird.api.schemas import FolderImportCreate

    stream_id, zone_id = _add_real_stream_and_zone(fresh_repository)
    folder = tmp_path / "folder-import"
    folder.mkdir()
    (folder / "first.png").write_bytes(b"real folder bytes one")
    (folder / "second.png").write_bytes(b"real folder bytes two")

    result = fresh_repository.import_folder_media(
        FolderImportCreate(folder_path=str(folder), stream_id=stream_id, zone_id=zone_id)
    )
    assert result.review_queue_count == 2


async def test_model_adapter_family_response_counts_exclude_demo_activity(
    client: httpx.AsyncClient, fresh_repository: ProductRepository,
) -> None:
    """`run_model_adapter`, `create_demo_detection_run`, and
    `decide_detection_proposal` are three independent `review_queue_count`
    producers (Model Adapters, the Manual Import/Streams "demo proposal"
    action, and Detection Proposals) that never create a Visit themselves
    -- their count should read the one real Visit imported below,
    throughout, regardless of how many proposal-only actions run against
    it."""

    stream_id, zone_id = _add_real_stream_and_zone(fresh_repository)
    imported = await client.post(
        "/api/media/import",
        data={
            "stream_id": stream_id,
            "zone_id": zone_id,
            "subject_label": "unknown_bird",
        },
        files={"file": ("adapter-family.png", b"model adapter family bytes", "image/png")},
    )
    assert imported.status_code == 201
    media_asset_id = imported.json()["media_asset"]["id"]

    adapter_response = await client.post(
        "/api/model-adapters/demo_rule_detector/runs",
        json={
            "adapter_id": "demo_rule_detector",
            "media_asset_id": media_asset_id,
            "zone_ids": [zone_id],
            "requested_labels": ["bird"],
        },
    )
    assert adapter_response.status_code == 200
    assert adapter_response.json()["review_queue_count"] == 1

    demo_run_response = await client.post(
        "/api/detection-runs/demo",
        json={
            "media_asset_id": media_asset_id,
            "label": "bird",
            "confidence": 0.72,
            "suggested_subject_label": "unknown_bird",
        },
    )
    assert demo_run_response.status_code == 201
    assert demo_run_response.json()["review_queue_count"] == 1

    proposal_response = await client.post(
        "/api/detection-proposals",
        json={
            "media_asset_id": media_asset_id,
            "stream_id": stream_id,
            "zone_id": zone_id,
            "label": "animal_candidate",
            "confidence": 0.82,
            "suggested_event_type": "animal_visit",
            "suggested_subject_label": "unknown_bird",
        },
    )
    assert proposal_response.status_code == 201
    proposal_id = proposal_response.json()["id"]

    decision_response = await client.post(
        f"/api/detection-proposals/{proposal_id}/decision",
        json={"decision": "reject", "notes": "Not outdoor activity."},
    )
    assert decision_response.status_code == 200
    assert decision_response.json()["review_queue_count"] == 1


# --- Analytics & Local Data Truth Consistency v1 ----------------------------


def test_demo_only_install_reports_no_genuine_analytics_activity(
    fresh_repository: ProductRepository,
) -> None:
    """`AnalyticsSummary` is `AnalyticsPage.tsx`'s own "Events"/"Visits"/
    "Needs review"/"Reviewed species" headline -- a demo-only install (zero
    real cameras) must report zero genuine activity, not the seeded demo
    Source's own two fabricated Events/Visits (one needs-review bird guess,
    one already-reviewed squirrel)."""

    with fresh_repository.session_factory() as session:
        summary = fresh_repository._analytics_summary(session)

    assert summary.event_count == 0
    assert summary.visit_count == 0
    assert summary.needs_review_count == 0
    assert summary.species_counts == {}
    assert summary.species_label_ids == []
    assert summary.zone_activity_counts == {}


def test_demo_only_install_local_data_status_excludes_activity_but_keeps_storage_inventory(
    fresh_repository: ProductRepository,
) -> None:
    """`LocalDataStatus` mixes two field families on one page
    (`LocalDataPage.tsx`): a genuine-activity family reused directly from
    `_analytics_summary` (`event_count`/`visit_count`/`needs_review_count`
    -- "outdoor activity"/"reviewable observations"/"local correction
    work"), and a raw local-storage-inventory family (`source_count`/
    `stream_count`/`zone_count`/`review_label_count`/`dataset_export_count`
    -- "local source records"/"local import references", the same
    "Local-first storage" framing as the page's own header). Only the first
    family is genuine ecosystem/history truth; the second legitimately
    describes what a first-run walkthrough deliberately seeds into local
    storage -- already honestly disclosed via `seed_data_present`, exactly
    like `AdapterEvaluationSummary.unreviewed_count` was already judged a
    legitimate non-"needs review" metric. See this milestone's own closure
    report for the complete contract."""

    with fresh_repository.session_factory() as session:
        status = fresh_repository._local_data_status(session)

    assert status.event_count == 0
    assert status.visit_count == 0
    assert status.needs_review_count == 0

    assert status.seed_data_present is True
    assert status.source_count == 1
    assert status.stream_count == 1
    assert status.zone_count == 3
    assert status.review_label_count == 1
    assert status.dataset_export_count == 1


def test_demo_only_install_reports_no_genuine_dataset_coverage(
    fresh_repository: ProductRepository,
) -> None:
    """`DatasetCoveragePanel.tsx` frames every field here as the user's own
    reviewed-dataset export readiness ("Export-ready reviewed records",
    "Reviewed species coverage") -- the seeded demo Source's already-
    reviewed squirrel Visit must not count as if the user had reviewed
    anything, and no species entry may show nonzero coverage from it."""

    with fresh_repository.session_factory() as session:
        coverage = fresh_repository._dataset_coverage_summary(session)

    assert coverage.reviewed_record_count == 0
    assert coverage.export_ready_count == 0
    assert coverage.needs_review_count == 0
    assert coverage.unknown_bird_count == 0
    assert coverage.unknown_animal_count == 0
    assert coverage.false_positive_count == 0
    assert coverage.reviewed_species_count == 0
    assert coverage.covered_target_species_count == 0
    assert all(item.reviewed_record_count == 0 for item in coverage.species)


def test_demo_only_install_reports_no_genuine_dataset_quality_issues(
    fresh_repository: ProductRepository,
) -> None:
    """`DatasetQualityPanel.tsx` frames every field here as the user's own
    export-cleanup signal ("Records needing cleanup before export") -- the
    seeded demo Source's own needs-review bird guess must not appear as a
    genuine QA issue."""

    with fresh_repository.session_factory() as session:
        quality = fresh_repository._dataset_quality_summary(session)

    assert quality.issue_count == 0
    assert quality.export_ready_count == 0
    assert quality.needs_review_count == 0
    assert quality.issues == []


def test_demo_only_install_yard_map_shows_no_genuine_activity_on_the_demo_stream_tile(
    fresh_repository: ProductRepository,
) -> None:
    """`YardMapPage.tsx` renders every Stream's tile identically, seeded or
    real -- there is no demo filter at the frontend at all
    (`YardMapActivitySummary` carries no `is_demo` field). The seeded demo
    Stream's own fabricated needs-review bird Visit must not appear as a
    clickable "N needs review" button, a fake "Latest"/"Confirmed" label,
    or a fabricated preview photo. The seeded demo Events are fixed at
    2026-01-15; pinning `now` just after that date proves the exclusion
    itself, independent of today's real wall-clock date already aging that
    fixed data out of "last_7_days" incidentally."""

    from datetime import UTC, datetime

    yard_map = fresh_repository.yard_map(
        activity_range="last_7_days",
        now=datetime(2026, 1, 15, 16, 0, tzinfo=UTC),
    )
    demo_stream = next(s for s in yard_map.streams if s.id == demo_data.STREAM_ID)

    assert demo_stream.activity.needs_review_count == 0
    assert demo_stream.activity.needs_review_visit_ids == []
    assert demo_stream.activity.latest_visit_id is None
    assert demo_stream.activity.latest_visit_at is None
    assert demo_stream.activity.latest_confirmed_label is None
    assert demo_stream.activity.latest_preview_url is None
    assert demo_stream.activity.open_activity_session is False


def test_analytics_and_dataset_summaries_count_only_real_activity_alongside_demo(
    fresh_repository: ProductRepository,
) -> None:
    """`AnalyticsSummary`, `DatasetCoverageSummary`, and `LocalDataStatus`'s
    reused fields must count exactly the real activity present, growing as
    it grows, never inflated or masked by the seeded demo Source's own
    fabricated Events/Visits alongside it. Uses a *reviewed* target-species
    Visit (unlike `_add_real_needs_review_visit`) so the derived
    `reviewed_species_count`/`covered_target_species_count` numerators are
    exercised too, not just the headline counts."""

    from datetime import UTC, datetime, timedelta

    from mockingbird.storage.models import EventModel, VisitModel

    stream_id, zone_id = _add_real_stream_and_zone(fresh_repository, suffix="analytics-1")
    started_at = datetime.now(UTC) - timedelta(minutes=10)
    with fresh_repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id="event-truth-consistency-reviewed-1", stream_id=stream_id,
                    title="Real activity", event_type="observation_engine_candidate",
                    started_at=started_at, ended_at=started_at + timedelta(seconds=5),
                    primary_zone_id=zone_id, review_status="reviewed",
                )
            )
            session.add(
                VisitModel(
                    id="visit-truth-consistency-reviewed-1", event_id="event-truth-consistency-reviewed-1",
                    subject_label="bird", species_guess="northern_cardinal", confidence=0.9,
                    reviewed_label="northern_cardinal", review_status="reviewed",
                    zone_id=zone_id, is_superseded=False,
                )
            )

    with fresh_repository.session_factory() as session:
        analytics = fresh_repository._analytics_summary(session)
        coverage = fresh_repository._dataset_coverage_summary(session)
        local_data = fresh_repository._local_data_status(session)

    assert analytics.event_count == 1
    assert analytics.visit_count == 1
    assert analytics.needs_review_count == 0
    assert analytics.species_counts == {"northern_cardinal": 1}
    assert analytics.species_label_ids == ["northern_cardinal"]

    assert coverage.reviewed_record_count == 1
    assert coverage.export_ready_count == 1
    assert coverage.reviewed_species_count == 1
    assert coverage.covered_target_species_count == 1

    assert local_data.event_count == 1
    assert local_data.visit_count == 1
    assert local_data.needs_review_count == 0

    # Grows correctly as more real activity is added -- never hardcoded.
    _add_real_needs_review_visit(
        fresh_repository, stream_id=stream_id, zone_id=zone_id,
        event_id="event-truth-consistency-reviewed-2", visit_id="visit-truth-consistency-reviewed-2",
        species_guess="blue_jay",
    )
    with fresh_repository.session_factory() as session:
        analytics = fresh_repository._analytics_summary(session)
    assert analytics.event_count == 2
    assert analytics.visit_count == 2
    assert analytics.needs_review_count == 1


def test_dataset_coverage_excludes_a_reviewed_target_species_added_under_the_demo_stream(
    fresh_repository: ProductRepository,
) -> None:
    """Proves the *derived* `covered_target_species_count`/`reviewed_
    species_count` numerators exclude demo-sourced activity, not only the
    headline counts (product-doctrine.md's own "0 real observations
    alongside 3 species observed" contradiction) -- inserting a Visit
    reviewed as a real target bird species directly under the seeded demo
    Stream must not mark `northern_cardinal` as covered."""

    from datetime import UTC, datetime, timedelta

    from mockingbird.storage.models import EventModel, VisitModel

    started_at = datetime.now(UTC) - timedelta(minutes=10)
    with fresh_repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id="event-demo-extra-cardinal", stream_id=demo_data.STREAM_ID,
                    title="Extra demo activity", event_type="bird_feeder_visit",
                    started_at=started_at, ended_at=started_at + timedelta(seconds=5),
                    primary_zone_id=demo_data.FEEDER_ZONE_ID, review_status="reviewed",
                )
            )
            session.add(
                VisitModel(
                    id="visit-demo-extra-cardinal", event_id="event-demo-extra-cardinal",
                    subject_label="bird", species_guess="northern_cardinal", confidence=0.9,
                    reviewed_label="northern_cardinal", review_status="reviewed",
                    zone_id=demo_data.FEEDER_ZONE_ID, is_superseded=False,
                )
            )

    with fresh_repository.session_factory() as session:
        coverage = fresh_repository._dataset_coverage_summary(session)

    assert coverage.covered_target_species_count == 0
    assert coverage.reviewed_species_count == 0
    cardinal = next(item for item in coverage.species if item.label == "northern_cardinal")
    assert cardinal.reviewed_record_count == 0


def test_yard_map_counts_real_stream_activity_normally_alongside_an_untouched_demo_tile(
    fresh_repository: ProductRepository,
) -> None:
    """A real Stream's own tile must show its genuine needs-review activity
    exactly as before, unaffected by the seeded demo Stream sitting
    alongside it on the same map."""

    stream_id, zone_id = _add_real_stream_and_zone(fresh_repository, suffix="yard-map-1")
    _add_real_needs_review_visit(
        fresh_repository, stream_id=stream_id, zone_id=zone_id,
        event_id="event-yard-map-real-1", visit_id="visit-yard-map-real-1",
    )

    yard_map = fresh_repository.yard_map(activity_range="last_7_days")
    real_stream = next(s for s in yard_map.streams if s.id == stream_id)
    demo_stream = next(s for s in yard_map.streams if s.id == demo_data.STREAM_ID)

    assert real_stream.activity.needs_review_count == 1
    assert real_stream.activity.needs_review_visit_ids == ["visit-yard-map-real-1"]
    assert demo_stream.activity.needs_review_count == 0


def test_repurposed_demo_source_counts_toward_analytics_and_dataset_summaries(
    fresh_repository: ProductRepository,
) -> None:
    """`de_demo_seeded_source` performs the real product repurposing
    mechanism (a real `SourceProviderConfigurationModel` row) -- once
    applied, the seeded demo Source's own two pre-existing Visits must
    count as genuine activity everywhere, exactly like `GET /api/review-
    queue` and `_visible_review_queue_count` already established."""

    de_demo_seeded_source(fresh_repository)

    with fresh_repository.session_factory() as session:
        analytics = fresh_repository._analytics_summary(session)
        coverage = fresh_repository._dataset_coverage_summary(session)
        local_data = fresh_repository._local_data_status(session)

    assert analytics.event_count == 2
    assert analytics.visit_count == 2
    assert analytics.needs_review_count == 1
    assert analytics.species_counts == {"squirrel": 1}

    assert coverage.reviewed_record_count == 1
    assert coverage.export_ready_count == 1

    assert local_data.event_count == 2
    assert local_data.visit_count == 2
    assert local_data.needs_review_count == 1


def test_repurposed_demo_source_counts_toward_yard_map_activity(
    fresh_repository: ProductRepository,
) -> None:
    """The same repurposing contract, proven for the Yard Map's own,
    differently-computed per-Stream `needs_review_count`."""

    from datetime import UTC, datetime

    de_demo_seeded_source(fresh_repository)

    yard_map = fresh_repository.yard_map(
        activity_range="last_7_days",
        now=datetime(2026, 1, 15, 16, 0, tzinfo=UTC),
    )
    demo_stream = next(s for s in yard_map.streams if s.id == demo_data.STREAM_ID)

    assert demo_stream.activity.needs_review_count == 1
    assert demo_stream.activity.needs_review_visit_ids == ["visit-bird-feeder-001"]


def test_dataset_quality_summary_does_not_crash_on_a_genuinely_eventless_real_event(
    fresh_repository: ProductRepository,
) -> None:
    """Latent pre-existing bug, found while adding this milestone's own
    demo-filtering to `_dataset_quality_summary`: unlike its siblings
    `_analytics_summary`/`_dataset_coverage_summary`, it never defined
    `event_ids_with_any_visits` (the ALL-time, including-superseded
    complement to `event_ids_with_visits`), so any genuinely eventless
    Event -- one that never had a Visit at all, e.g. "Motion ignored in
    privacy zone" (product-doctrine.md's own Activity Session example) --
    raised `NameError`, crashing `GET /api/dataset-quality/summary`. Not a
    demo-truth defect (it would crash identically for real data), but
    found directly inside, and fixed alongside, code this milestone was
    already required to touch; disclosed in the closure report rather than
    silently folded in."""

    from datetime import UTC, datetime, timedelta

    from mockingbird.storage.models import EventModel

    stream_id, zone_id = _add_real_stream_and_zone(fresh_repository, suffix="eventless-1")
    started_at = datetime.now(UTC) - timedelta(minutes=10)
    with fresh_repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id="event-genuinely-eventless-1", stream_id=stream_id,
                    title="Motion ignored", event_type="ignored_motion",
                    started_at=started_at, ended_at=started_at + timedelta(seconds=2),
                    primary_zone_id=zone_id, review_status="reviewed",
                )
            )

    with fresh_repository.session_factory() as session:
        quality = fresh_repository._dataset_quality_summary(session)

    assert quality.issue_count == 1
    assert quality.needs_review_count == 1
    assert quality.issues[0].target_type == "event"
    assert quality.issues[0].target_id == "event-genuinely-eventless-1"


# ---------------------------------------------------------------------------
# UI/UX & First-Run Adoption v1: Place-history, discovery, and export
# surfaces. That milestone's own fresh-install walkthrough found Today and
# Place Report rendering "Kinds of wildlife known here: 1" (the seeded demo
# squirrel) and Place Story naming it the Place's first recorded species,
# with the demo Visit also flowing into Activity Library, reviewed dataset
# exports, and research-safe (Darwin Core/Camtrap DP/iNaturalist) scope.
# Analytics & Local Data Truth Consistency v1 had explicitly left the Place
# Biodiversity family out of its own bounded scope. Fixed once at
# `_historical_place_baseline_and_species_statuses` (all six Place-history
# callers) plus each surface's own Stream scope, all via the same
# `_real_stream_ids`/`_real_source_condition()` seam.
# ---------------------------------------------------------------------------


async def test_fresh_install_biodiversity_summary_knows_no_wildlife(client) -> None:
    response = await client.get("/api/place/biodiversity-summary")
    assert response.status_code == 200
    body = response.json()
    assert body["historical_baseline"]["distinct_taxa_count"] == 0
    assert body["historical_baseline"]["earliest_authoritative_record_at"] is None
    assert body["taxa"] == []


async def test_fresh_install_place_story_has_no_demo_wildlife_history(client) -> None:
    response = await client.get("/api/place/story")
    assert response.status_code == 200
    text = response.text.lower()
    assert "squirrel" not in text


async def test_fresh_install_place_activity_report_has_no_demo_wildlife(client) -> None:
    response = await client.post(
        "/api/analytics/place-activity-report",
        json={"start_at": "2026-01-01T00:00:00Z", "end_at": "2026-02-01T00:00:00Z"},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert "squirrel" not in response.text.lower()
    assert body["historical_baseline"]["distinct_taxa_count"] == 0


async def test_fresh_install_activity_library_has_no_demo_visits(client) -> None:
    response = await client.post("/api/activity-library/search", json={})
    assert response.status_code == 200, response.text
    assert "visit-squirrel-ground-001" not in response.text
    assert "visit-bird-feeder-001" not in response.text


async def test_fresh_install_reviewed_dataset_export_has_no_demo_records(client) -> None:
    response = await client.post("/api/dataset-exports", json={"name": "First export"})
    assert response.status_code == 201, response.text
    assert response.json()["export"]["record_count"] == 0


async def test_fresh_install_research_scope_never_includes_demo_visits(client) -> None:
    research = await client.post("/api/research/export", json={"dry_run": True})
    assert research.status_code == 201, research.text
    assert research.json()["observation_count"] == 0
    assert research.json()["excluded_count"] == 0

    preview = await client.post(
        "/api/ecological/eligibility-preview", json={"destination": "inaturalist"}
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["items"] == []


async def test_repurposed_demo_source_counts_toward_place_biodiversity(
    client, fresh_repository: ProductRepository
) -> None:
    """Positive control: exclusion follows the *effective* provider, so the
    same seeded history reappears once the Source is genuinely real."""

    de_demo_seeded_source(fresh_repository)
    response = await client.get("/api/place/biodiversity-summary")
    assert response.status_code == 200
    body = response.json()
    assert body["historical_baseline"]["distinct_taxa_count"] == 1
    assert [taxon["label"] for taxon in body["taxa"]] == ["squirrel"]
