"""Remaining Performance P1 Closure v1 -- P1-7 and P1-8.

Performance / Scale / Stability Closure v1 measured, root-caused and then
deliberately did *not* close two blockers, because both needed a
coordinated frontend change it was not authorised to make:

- **P1-7**: `GET /api/media` returned every MediaAsset ever recorded --
  11,244 rows and **11.9 MB** at the accepted Profile B workload, ~47 MB at
  Profile D -- to eight product pages, none of which needed the library.
  Seven of them only wanted a lookup map or a picker; the eighth
  (`StreamDetailPage`) downloaded all of it to run a two-clause filter in
  the browser.
- **P1-8**: `GET /api/detection-proposals` (2,811 rows / 1.40 MB),
  `GET /api/detection-runs` (2,811 rows / 539 KB) and
  `GET /api/species-suggestions` (2,464 rows / 1.50 MB) were read whole by
  the Review Queue, the Streams timeline and their own pages, which then
  related each row to an *already bounded* set of work in the browser.

What these tests pin is the structural property, never a wall-clock
threshold: **ordinary product retrieval scales with the requested window,
not with total accumulated history.** The sharpest form of that is
`test_*_does_not_grow_with_history`, which builds the same library twice at
two very different sizes and asserts the product-shaped read returns the
same number of rows and issues the same number of SQL statements.

They also pin the two things a bound can quietly break, and which this
milestone was explicitly required not to break:

- **totals stay totals** -- every value the accepted UI labels as a total
  (the Model Adapters "Saved images" row, the Streams "Saved images" row,
  the Detection Proposals filter chips, the Species Suggestions badge) is
  computed by the server over the whole matching set, never by counting a
  downloaded window;
- **predicates are ported, not approximated** -- `image_only` returns
  exactly the rows `StreamDetailPage.streamImageMediaAssets` used to keep,
  including the awkward case of a non-image `media_type` carrying an
  `image/` content type.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import event as sa_event
from tests.conftest import LegacyAuthenticatedSyncTestClient

from mockingbird.api.main import (
    _DEFAULT_LIST_PAGE_SIZE,
    _MAX_LIST_PAGE_SIZE,
    app,
    configure_repository,
)
from mockingbird.api.schemas import DetectionProposalStatus
from mockingbird.repository.product_repository import (
    ProductRepository,
    SpeciesSuggestionModel,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    DetectionProposalModel,
    DetectionRunModel,
    MediaAssetModel,
    StreamModel,
)


SOURCE_ID = "source-p1"
STREAM_IDS = ("stream-p1-a", "stream-p1-b")
_NOW = datetime(2026, 9, 24, 8, 0, tzinfo=UTC)

# One in every `_VIDEO_EVERY` assets is a video rather than an image, and
# one video in every `_IMAGE_CONTENT_TYPE_VIDEO_EVERY` of those carries an
# `image/` content type anyway -- the real shape the browser predicate had
# to cope with, and the one an "only media_type == image" port would miss.
_VIDEO_EVERY = 3
_IMAGE_CONTENT_TYPE_VIDEO_EVERY = 2

_PROPOSAL_STATUSES = ("proposed", "accepted", "rejected", "converted")


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'p1.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)
    repository.close()


@pytest.fixture
def client(repository: ProductRepository) -> LegacyAuthenticatedSyncTestClient:
    return LegacyAuthenticatedSyncTestClient(app)


def _build(repository: ProductRepository, *, media_count: int) -> None:
    """A library shaped like the accepted workload: media per Stream, with a
    DetectionRun, a DetectionProposal and a SpeciesSuggestion per asset."""

    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID,
                    name="P1 Camera",
                    kind="integration",
                    status="connected",
                    description="P1 fixture.",
                )
            )
            for stream_id in STREAM_IDS:
                session.add(
                    StreamModel(
                        id=stream_id,
                        source_id=SOURCE_ID,
                        name=stream_id,
                        description="P1 fixture stream.",
                        is_live=True,
                    )
                )
            for index in range(media_count):
                stream_id = STREAM_IDS[index % len(STREAM_IDS)]
                is_video = index % _VIDEO_EVERY == 0
                media_type = "video" if is_video else "image"
                if is_video and index % _IMAGE_CONTENT_TYPE_VIDEO_EVERY == 0:
                    content_type = "image/png"
                elif is_video:
                    content_type = "video/mp4"
                else:
                    content_type = "image/jpeg"
                media_id = f"p1-media-{index:05d}"
                created_at = _NOW + timedelta(minutes=index)
                session.add(
                    MediaAssetModel(
                        id=media_id,
                        source_id=SOURCE_ID,
                        stream_id=stream_id,
                        filename=f"{media_id}.bin",
                        content_type=content_type,
                        media_type=media_type,
                        local_path=f"/var/mockingbird/{media_id}.bin",
                        original_filename=f"{media_id}.bin",
                        file_size_bytes=1024,
                        created_at=created_at,
                    )
                )
                session.add(
                    DetectionRunModel(
                        id=f"p1-run-{index:05d}",
                        media_asset_id=media_id,
                        source="manual",
                        status="completed",
                        summary="P1 fixture run.",
                        created_at=created_at,
                    )
                )
                session.add(
                    DetectionProposalModel(
                        id=f"p1-proposal-{index:05d}",
                        run_id=f"p1-run-{index:05d}",
                        media_asset_id=media_id,
                        stream_id=stream_id,
                        label="animal",
                        confidence=0.75,
                        suggested_event_type="animal_visit",
                        suggested_subject_label="unknown_animal",
                        status=_PROPOSAL_STATUSES[index % len(_PROPOSAL_STATUSES)],
                        visit_id=f"p1-visit-{index:05d}" if index % 4 == 0 else None,
                        event_id=f"p1-event-{index:05d}" if index % 4 == 1 else None,
                        created_at=created_at,
                    )
                )
                session.add(
                    SpeciesSuggestionModel(
                        id=f"p1-suggestion-{index:05d}",
                        source_id=SOURCE_ID,
                        stream_id=stream_id,
                        media_asset_id=media_id,
                        visit_id=None,
                        event_id=None,
                        adapter_id="p1-adapter",
                        adapter_name="P1 fixture classifier",
                        suggested_label="northern_cardinal",
                        confidence=0.6,
                        rank=1,
                        alternatives_json="[]",
                        status="pending",
                        created_at=created_at,
                    )
                )


def _count_statements(repository: ProductRepository, call):
    counter = {"n": 0}

    def _on_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        counter["n"] += 1

    sa_event.listen(repository.engine, "before_cursor_execute", _on_execute)
    try:
        result = call()
    finally:
        sa_event.remove(repository.engine, "before_cursor_execute", _on_execute)
    return counter["n"], result


# --------------------------------------------------------------------------
# P1-7 -- GET /api/media
# --------------------------------------------------------------------------


def test_media_list_defaults_to_a_bounded_page(client, repository) -> None:
    """The legacy route can no longer return the whole library by accident.

    This is the structural backstop: even a caller that asks for nothing
    gets one page, exactly as `GET /api/visits` and `GET /api/events` were
    given by this milestone's parent."""

    _build(repository, media_count=_DEFAULT_LIST_PAGE_SIZE + 61)

    response = client.get("/api/media")
    assert response.status_code == 200
    assert len(response.json()) == _DEFAULT_LIST_PAGE_SIZE

    over_max = client.get("/api/media", params={"limit": _MAX_LIST_PAGE_SIZE + 1})
    assert over_max.status_code == 422


def test_media_page_window_is_bounded_while_counts_stay_totals(client, repository) -> None:
    """A bounded window must not turn a total into a window count.

    The Model Adapters page prints `image_count` as "Saved images", and the
    Streams page prints a per-Stream `image_count` the same way."""

    _build(repository, media_count=400)

    response = client.get("/api/media/page", params={"limit": 25})
    assert response.status_code == 200
    page = response.json()

    assert len(page["items"]) == 25
    assert page["total_count"] == 400
    assert page["has_more"] is True

    every_image = sum(
        1 for asset in repository.list_media_assets(limit=None) if asset.media_type == "image"
    )
    assert page["image_count"] == every_image
    # The window is deliberately far smaller than the total it reports.
    assert page["image_count"] > len(page["items"])


def test_media_page_never_exposes_a_local_path(client, repository) -> None:
    """The bounded read carries the same redaction the unbounded one had."""

    _build(repository, media_count=5)

    page = client.get("/api/media/page").json()
    assert page["items"]
    assert all(asset["local_path"] == "" for asset in page["items"])


def test_media_page_paging_covers_the_library_exactly_once(repository) -> None:
    _build(repository, media_count=137)

    seen: list[str] = []
    offset = 0
    while True:
        page = repository.media_asset_page(limit=20, offset=offset)
        seen.extend(asset.id for asset in page.items)
        if not page.has_more:
            break
        offset += 20

    assert len(seen) == 137
    assert len(set(seen)) == 137


def test_media_image_only_matches_the_ported_browser_predicate(repository) -> None:
    """`image_only` is a port of `streamImageMediaAssets`, not a rewrite.

    That predicate kept an asset whose `media_type` is `image` *or* whose
    `content_type` starts with `image/`. The fixture deliberately contains
    videos of the second kind, so a narrower server-side filter fails here."""

    _build(repository, media_count=120)
    stream_id = STREAM_IDS[0]

    everything = repository.list_media_assets(limit=None)
    expected = sorted(
        asset.id
        for asset in everything
        if asset.stream_id == stream_id
        and (asset.media_type == "image" or asset.content_type.startswith("image/"))
    )
    # The fixture must actually contain the awkward case, or this proves nothing.
    assert any(
        asset.media_type != "image" and asset.content_type.startswith("image/")
        for asset in everything
        if asset.stream_id == stream_id
    )

    page = repository.media_asset_page(
        stream_id=stream_id, image_only=True, limit=len(everything)
    )
    assert sorted(asset.id for asset in page.items) == expected
    assert page.total_count == len(expected)
    # And newest-first, which the browser used to sort for itself.
    assert [asset.id for asset in page.items] == sorted(
        (asset.id for asset in page.items), reverse=True
    )


def test_media_hydration_returns_exactly_the_referenced_assets(client, repository) -> None:
    """The two-pass hydration that replaced the browser-side `mediaById` maps."""

    _build(repository, media_count=300)
    wanted = ["p1-media-00007", "p1-media-00123", "p1-media-00299"]

    response = client.get("/api/media/page", params=[("ids", one) for one in wanted])
    assert response.status_code == 200
    page = response.json()
    assert sorted(asset["id"] for asset in page["items"]) == sorted(wanted)
    assert page["total_count"] == len(wanted)


def test_media_hydration_with_an_empty_id_set_stays_empty(repository) -> None:
    """An explicit "nothing referenced" must never degrade to "everything"."""

    _build(repository, media_count=50)

    page = repository.media_asset_page(ids=[], limit=100)
    assert page.items == []
    assert page.total_count == 0


@pytest.mark.parametrize("media_count", [60, 600])
def test_media_page_does_not_grow_with_history(tmp_path, media_count) -> None:
    """The invariant, stated directly: the same product-shaped read returns
    the same rows and issues the same number of statements whether the
    library holds 60 assets or ten times that.

    Pinned by row count and statement count, never by wall-clock."""

    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / f'p1-{media_count}.sqlite3'}",
        media_root=tmp_path / f"media-{media_count}",
    )
    try:
        _build(repository, media_count=media_count)
        statements, page = _count_statements(
            repository, lambda: repository.media_asset_page(limit=25)
        )
        assert len(page.items) == 25
        assert statements == 3, statements  # one window read, two aggregates
        assert page.total_count == media_count
    finally:
        repository.close()


# --------------------------------------------------------------------------
# P1-8 -- detection proposals / runs / species suggestions
# --------------------------------------------------------------------------


def test_detection_list_routes_default_to_a_bounded_page(client, repository) -> None:
    _build(repository, media_count=_DEFAULT_LIST_PAGE_SIZE + 44)

    for path in ("/api/detection-proposals", "/api/detection-runs"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert len(response.json()) == _DEFAULT_LIST_PAGE_SIZE, path


def test_species_suggestions_default_to_a_bounded_page_with_a_true_total(
    client, repository
) -> None:
    """The Species Suggestions page's badge reads `total_count`, so the
    bound must not make it describe the window."""

    total = _DEFAULT_LIST_PAGE_SIZE + 88
    _build(repository, media_count=total)

    body = client.get("/api/species-suggestions").json()
    assert len(body["species_suggestions"]) == _DEFAULT_LIST_PAGE_SIZE
    assert body["total_count"] == total
    assert body["has_more"] is True

    windowed = client.get("/api/species-suggestions", params={"limit": 10}).json()
    assert len(windowed["species_suggestions"]) == 10
    assert windowed["total_count"] == total


def test_species_suggestion_filters_count_only_their_own_matches(client, repository) -> None:
    _build(repository, media_count=40)

    body = client.get(
        "/api/species-suggestions",
        params={"media_asset_id": "p1-media-00011", "limit": 5},
    ).json()
    assert body["total_count"] == 1
    assert body["has_more"] is False
    assert [item["media_asset_id"] for item in body["species_suggestions"]] == [
        "p1-media-00011"
    ]


def test_detection_proposal_scope_is_the_browser_relation_ported(client, repository) -> None:
    """A proposal belongs to a queue item by Visit, by Event, or by
    MediaAsset -- `proposalRelationForReviewItem`, moved to the server and
    OR'd so one call answers a whole page of review work."""

    _build(repository, media_count=60)

    response = client.get(
        "/api/detection-proposals/page",
        params=[
            ("visit_ids", "p1-visit-00004"),
            ("event_ids", "p1-event-00005"),
            ("media_asset_ids", "p1-media-00050"),
        ],
    )
    assert response.status_code == 200
    page = response.json()
    assert sorted(item["id"] for item in page["items"]) == [
        "p1-proposal-00004",
        "p1-proposal-00005",
        "p1-proposal-00050",
    ]
    assert page["total_count"] == 3


def test_detection_run_scope_answers_both_review_queue_questions(client, repository) -> None:
    """"Which run produced this proposal" (`ids`) and "has this media been
    analysed at all" (`media_asset_ids`) are OR'd into one call."""

    _build(repository, media_count=60)

    page = client.get(
        "/api/detection-runs/page",
        params=[
            ("ids", "p1-run-00059"),
            ("media_asset_ids", "p1-media-00000"),
            ("media_asset_ids", "p1-media-00001"),
        ],
    ).json()
    assert sorted(item["id"] for item in page["items"]) == [
        "p1-run-00000",
        "p1-run-00001",
        "p1-run-00059",
    ]
    assert page["total_count"] == 3


def test_detection_proposal_status_counts_are_whole_scope_totals(client, repository) -> None:
    """The Detection Proposals page prints these on its filter chips.

    They are computed over the whole scope and are deliberately *not*
    narrowed by the active `status`, so every chip reports its own total
    even while the page holds one small window."""

    _build(repository, media_count=200)

    page = client.get(
        "/api/detection-proposals/page",
        params={"limit": 5, "status": DetectionProposalStatus.proposed.value},
    ).json()

    assert len(page["items"]) == 5
    assert all(item["status"] == "proposed" for item in page["items"])
    # `total_count` follows the status filter; the chips do not.
    assert page["total_count"] == 50
    assert page["status_counts"] == {
        "proposed": 50,
        "accepted": 50,
        "rejected": 50,
        "converted": 50,
    }
    assert sum(page["status_counts"].values()) == 200


def test_empty_detection_scope_stays_empty(repository) -> None:
    """A page with nothing to relate must read nothing, never everything."""

    _build(repository, media_count=50)

    assert repository.detection_proposal_page(media_asset_ids=[], limit=100).total_count == 0
    assert repository.detection_run_page(ids=[], limit=100).total_count == 0


@pytest.mark.parametrize("media_count", [60, 600])
def test_detection_reads_do_not_grow_with_history(tmp_path, media_count) -> None:
    """The same invariant as `test_media_page_does_not_grow_with_history`,
    for the Review Queue's page-scoped detection evidence: a fixed window of
    review work costs a fixed number of rows and statements no matter how
    much history sits behind it."""

    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / f'p1-det-{media_count}.sqlite3'}",
        media_root=tmp_path / f"media-det-{media_count}",
    )
    try:
        _build(repository, media_count=media_count)
        # One page of review work: the newest 25 assets, as the Review Queue
        # would scope its read.
        scope = [f"p1-media-{index:05d}" for index in range(media_count - 25, media_count)]

        proposal_statements, proposals = _count_statements(
            repository, lambda: repository.detection_proposal_page(media_asset_ids=scope, limit=500)
        )
        run_statements, runs = _count_statements(
            repository,
            lambda: repository.detection_run_page(
                ids=[proposal.run_id for proposal in proposals.items],
                media_asset_ids=scope,
                limit=500,
            ),
        )

        assert len(proposals.items) == 25
        assert proposals.total_count == 25
        assert len(runs.items) == 25
        assert proposal_statements == 3, proposal_statements  # window, total, grouped counts
        assert run_statements == 2, run_statements  # window, total
    finally:
        repository.close()


# --------------------------------------------------------------------------
# The frontend side of the same guarantee
# --------------------------------------------------------------------------


_WEB_SRC = Path(__file__).resolve().parents[1] / "web" / "src"
_UNBOUNDED_CLIENT_READS = (
    "getMediaAssets()",
    "getDetectionProposals()",
    "getDetectionRuns()",
)


def test_no_product_page_reads_a_whole_list_endpoint() -> None:
    """The structural guard against quietly reintroducing P1-7 / P1-8.

    The unbounded client helpers still exist -- they are the legacy contract
    and are still reachable -- but no page may call them. A page that needs
    MediaAssets, proposals or runs reads a bounded window, hydrates by id,
    or scopes to the work on screen. If this fails, a page has gone back to
    downloading the whole history.
    """

    offenders: list[str] = []
    for path in sorted(_WEB_SRC.rglob("*.tsx")) + sorted(_WEB_SRC.rglob("*.ts")):
        if path.name == "client.ts":
            continue
        text = path.read_text(encoding="utf-8")
        for call in _UNBOUNDED_CLIENT_READS:
            if f"apiClient.{call}" in text:
                offenders.append(f"{path.relative_to(_WEB_SRC)} calls apiClient.{call}")

    assert offenders == [], offenders
