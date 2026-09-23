"""Review Queue Scale Closure v1 -- the bounded Review Queue page.

The defect these tests lock down is the one release-blocking P0 that
Performance / Scale / Stability Closure v1 left open (its §R P0-4 and §Z):
`GET /api/review-queue` returned the whole queue, and the Review Queue page
asked for it with `include_reviewed=true` on mount *and after every saved
correction*, then computed every tab count, triage-filter count,
source/stream facet and "showing N of M" disclosure client-side over the
full download. Measured: 2,060 items / 14.9 MB / 74.4 s at the burst
profile; 2,813 items / 20.4 MB / 39.7 s for the page's own
`include_reviewed=true` request at Profile B.

Two things therefore have to hold at once, and both are tested here:

* **bounded** -- the page's response never grows with total history, and
  neither does the number of SQL statements behind it;
* **unchanged** -- the tabs, filters, ordering, counts, reviewed-history
  behaviour and demo-source semantics are exactly what the accepted UI had,
  because a bounded response presenting a window's numbers as totals would
  be a truth regression rather than a performance fix.

The count and payload assertions are structural, not wall-clock: payload
growth and statement counts are environment-independent, and "returns the
whole history again" is exactly a payload/statement fact.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from sqlalchemy import event as sa_event

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import (
    ReviewCorrectionCreate,
    ReviewQueuePageRequest,
    ReviewQueueProductTab,
    ReviewQueueSort,
    ReviewQueueStatusFilter,
    ReviewQueueTriageFilter,
    ReviewStatus,
    SourceKind,
    SourceStatus,
    VisitReviewReopenCreate,
)
from mockingbird.repository.product_repository import (
    MotionEvidenceModel,
    ProductRepository,
    SourceProviderConfigurationModel,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    StreamModel,
    VisitEvidenceLinkModel,
    VisitModel,
)
from tests.conftest import LegacyAuthenticatedTestClient, de_demo_seeded_source


SOURCE_ID = "source-queue-page"
STREAM_ID = "stream-queue-page"
SECOND_STREAM_ID = "stream-queue-page-2"
_NOW = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.anyio


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    instance = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(instance)
    yield instance
    configure_repository(None)


@pytest.fixture
async def client(repository: ProductRepository):
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(
        transport=transport, base_url="http://testserver"
    ) as api_client:
        yield api_client


def _add_streams(session) -> None:
    session.add(
        CameraSourceModel(
            id=SOURCE_ID,
            name="Queue Page Camera",
            kind=SourceKind.integration.value,
            status=SourceStatus.connected.value,
            description="Review Queue Scale Closure v1 fixture.",
        )
    )
    session.add(
        SourceProviderConfigurationModel(
            source_id=SOURCE_ID,
            provider_key="camera_node",
            config_json="{}",
            updated_at=_NOW,
        )
    )
    for stream_id, name in ((STREAM_ID, "Feeder"), (SECOND_STREAM_ID, "Birdbath")):
        session.add(
            StreamModel(
                id=stream_id,
                source_id=SOURCE_ID,
                name=name,
                description="Review Queue Scale Closure v1 fixture stream.",
                is_live=True,
            )
        )


def _add_visit(
    session,
    *,
    index: int,
    status: str,
    stream_id: str = STREAM_ID,
    subject_label: str = "bird",
    event_type: str = "observation_engine_candidate",
    species_guess: str | None = "Northern Cardinal",
    with_motion_evidence: bool = False,
) -> str:
    """One Visit with the evidence shape a real admitted Visit has."""

    event_id = f"event-{index:04d}"
    visit_id = f"visit-{index:04d}"
    asset_id = f"asset-{index:04d}"
    # Reviewed history is old and the backlog is recent -- the real shape of
    # an established install, and the shape that lets "does this scale with
    # history" be asked at all.
    started_at = (
        _NOW - timedelta(days=30) - timedelta(minutes=index)
        if status == ReviewStatus.reviewed.value
        else _NOW - timedelta(minutes=index)
    )
    session.add(
        EventModel(
            id=event_id,
            stream_id=stream_id,
            title=f"Queue page event {index}",
            event_type=event_type,
            started_at=started_at,
            ended_at=started_at + timedelta(seconds=30),
            primary_zone_id=None,
            review_status=status,
        )
    )
    session.add(
        MediaAssetModel(
            id=asset_id,
            source_id=SOURCE_ID,
            stream_id=stream_id,
            filename=f"{asset_id}.jpg",
            content_type="image/jpeg",
            media_type="image",
            local_path=f"queue-page/{asset_id}.jpg",
            original_filename=f"{asset_id}.jpg",
            file_size_bytes=1024,
            created_at=started_at,
            evidence_role="monitoring_frame",
            captured_at=started_at,
        )
    )
    session.add(
        VisitModel(
            id=visit_id,
            event_id=event_id,
            subject_label=subject_label,
            species_guess=species_guess,
            confidence=0.8,
            reviewed_label=(
                "Northern Cardinal" if status == ReviewStatus.reviewed.value else None
            ),
            review_status=status,
            representative_media_path=f"queue-page/{asset_id}.jpg",
            zone_id=None,
            is_superseded=False,
        )
    )
    session.add(
        VisitEvidenceLinkModel(
            id=f"link-{index:04d}",
            visit_id=visit_id,
            media_asset_id=asset_id,
            captured_at=started_at,
            frame_sequence=0,
            sort_order=0,
            is_primary=True,
            evidence_role="monitoring_frame",
            created_at=started_at,
        )
    )
    if with_motion_evidence:
        session.add(
            MotionEvidenceModel(
                id=f"motion-{index:04d}",
                source_id=SOURCE_ID,
                stream_id=stream_id,
                zone_id=None,
                start_frame_index=0,
                end_frame_index=2,
                best_frame_index=1,
                peak_changed_ratio=0.4,
                triggered_frame_count=2,
                scoring_config_json="{}",
                snapshot_media_asset_id=asset_id,
                status="promoted",
                promoted_event_id=event_id,
                promoted_visit_id=visit_id,
                created_at=started_at,
                notes=None,
            )
        )
    return visit_id


def _build_library(
    repository: ProductRepository,
    *,
    reviewed_visits: int,
    needs_review_visits: int,
    second_stream_needs_review: int = 0,
) -> None:
    with repository.session_factory() as session:
        with session.begin():
            _add_streams(session)
            index = 0
            for status, count in (
                (ReviewStatus.reviewed.value, reviewed_visits),
                (ReviewStatus.needs_review.value, needs_review_visits),
            ):
                for _ in range(count):
                    _add_visit(session, index=index, status=status)
                    index += 1
            for _ in range(second_stream_needs_review):
                _add_visit(
                    session,
                    index=index,
                    status=ReviewStatus.needs_review.value,
                    stream_id=SECOND_STREAM_ID,
                )
                index += 1


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


def _animals(**overrides) -> ReviewQueuePageRequest:
    """The page's own default view, plus overrides."""

    return ReviewQueuePageRequest(tab=ReviewQueueProductTab.animals, **overrides)


# --- pagination ------------------------------------------------------------


def test_first_page_is_bounded_and_reports_whole_queue_totals(
    repository: ProductRepository,
) -> None:
    _build_library(repository, reviewed_visits=10, needs_review_visits=60)

    page = repository.review_queue_page(_animals(page_size=25))

    assert len(page.items) == 25
    assert page.page == 0
    assert page.page_size == 25
    assert page.matching_items == 60
    assert page.page_count == 3
    # Totals describe the whole visible queue, not the page.
    assert page.total_items == 70
    assert page.tab_counts.animals == 60
    assert page.tab_counts.reviewed == 10
    assert page.pending_review_count == 60
    # Page items are full review cards: the hydration a displayed card needs.
    assert all(item.review_state_token for item in page.items)
    assert all(item.identification is not None for item in page.items)


def test_paging_covers_every_item_exactly_once(repository: ProductRepository) -> None:
    """No duplicates between pages, and nothing skipped while traversing."""

    _build_library(repository, reviewed_visits=5, needs_review_visits=57)

    seen: list[str] = []
    page_index = 0
    while True:
        page = repository.review_queue_page(_animals(page=page_index, page_size=10))
        seen.extend(item.id for item in page.items)
        page_index += 1
        if page_index >= page.page_count:
            break

    assert len(seen) == 57
    assert len(set(seen)) == 57

    whole = repository.review_queue_page(_animals(page_size=100))
    assert [item.id for item in whole.items] == seen


def test_page_order_matches_the_unbounded_queue_order(
    repository: ProductRepository,
) -> None:
    """Deterministic ordering, and the same order the old endpoint produced."""

    _build_library(repository, reviewed_visits=3, needs_review_visits=30)

    unbounded = [
        item
        for item in repository.review_queue_items(include_reviewed=True)
        if not item.is_demo_source
        and item.review_status is ReviewStatus.needs_review
        and item.product_category == "animal"
    ]
    paged: list[str] = []
    for page_index in range(3):
        page = repository.review_queue_page(_animals(page=page_index, page_size=10))
        paged.extend(item.id for item in page.items)

    assert paged == [item.id for item in unbounded]
    # And repeating the same request gives the same window.
    first = repository.review_queue_page(_animals(page_size=10))
    again = repository.review_queue_page(_animals(page_size=10))
    assert [item.id for item in first.items] == [item.id for item in again.items]


def test_page_beyond_the_last_page_clamps_instead_of_returning_nothing(
    repository: ProductRepository,
) -> None:
    _build_library(repository, reviewed_visits=0, needs_review_visits=30)

    page = repository.review_queue_page(_animals(page=99, page_size=25))

    assert page.page == 1
    assert page.page_count == 2
    assert len(page.items) == 5


def test_empty_queue(repository: ProductRepository) -> None:
    page = repository.review_queue_page(_animals())

    assert page.items == []
    assert page.total_items == 0
    assert page.matching_items == 0
    assert page.page_count == 1
    assert page.pending_review_count == 0
    assert page.tab_counts.animals == 0


def test_queue_smaller_than_one_page(repository: ProductRepository) -> None:
    _build_library(repository, reviewed_visits=2, needs_review_visits=3)

    page = repository.review_queue_page(_animals(page_size=25))

    assert len(page.items) == 3
    assert page.matching_items == 3
    assert page.page_count == 1


# --- bounded cost ----------------------------------------------------------


def test_response_and_statements_do_not_grow_with_total_history(
    tmp_path: Path,
) -> None:
    """The regression test for the P0 itself.

    Ten times the accumulated history, the same page size: the response
    must stay the same size and the request must not issue ten times the
    statements. This is what would fail if the Review Queue ever silently
    returned to whole-history hydration.
    """

    small = ProductRepository(db_url=f"sqlite:///{tmp_path / 'small.sqlite3'}")
    large = ProductRepository(db_url=f"sqlite:///{tmp_path / 'large.sqlite3'}")
    try:
        # Identical *backlog*, ten times the reviewed *history* -- which is
        # exactly the shape the P0 was about: "the product gets slower every
        # day it runs".
        _build_library(small, reviewed_visits=30, needs_review_visits=40)
        _build_library(large, reviewed_visits=300, needs_review_visits=40)

        small_statements, small_page = _count_statements(
            small, lambda: small.review_queue_page(_animals(page_size=25))
        )
        large_statements, large_page = _count_statements(
            large, lambda: large.review_queue_page(_animals(page_size=25))
        )

        assert len(small_page.items) == len(large_page.items) == 25
        # Totals still tell the truth about each library.
        assert small_page.matching_items == large_page.matching_items == 40
        assert small_page.tab_counts.reviewed == 30
        assert large_page.tab_counts.reviewed == 300

        small_bytes = len(small_page.model_dump_json())
        large_bytes = len(large_page.model_dump_json())
        # Payload is a function of page size, not of database size. The only
        # growth allowed is the extra digits in `tab_counts.reviewed`.
        assert abs(large_bytes - small_bytes) < 64, (small_bytes, large_bytes)

        # A per-item cascade over the whole library would be ~10x here.
        assert large_statements < small_statements * 2, (
            small_statements,
            large_statements,
        )
    finally:
        small.engine.dispose()
        large.engine.dispose()


def test_only_the_bounded_fast_review_snapshot_grows_with_the_backlog(
    tmp_path: Path,
) -> None:
    """A ten-times-larger *backlog*, not history, is still bounded.

    The one part of the response that grows with the backlog at all is the
    Fast Review target snapshot, and it saturates at its own documented
    200-target ceiling -- ~11 KB of identifiers, against the 14.9 MB the
    unbounded endpoint returned at the burst profile.
    """

    small = ProductRepository(db_url=f"sqlite:///{tmp_path / 'small.sqlite3'}")
    large = ProductRepository(db_url=f"sqlite:///{tmp_path / 'large.sqlite3'}")
    try:
        _build_library(small, reviewed_visits=0, needs_review_visits=250)
        _build_library(large, reviewed_visits=0, needs_review_visits=2500)

        small_page = small.review_queue_page(_animals(page_size=25))
        large_page = large.review_queue_page(_animals(page_size=25))

        assert len(small_page.fast_review_targets) == 200
        assert len(large_page.fast_review_targets) == 200
        small_bytes = len(small_page.model_dump_json())
        large_bytes = len(large_page.model_dump_json())
        assert abs(large_bytes - small_bytes) < 64, (small_bytes, large_bytes)
    finally:
        small.engine.dispose()
        large.engine.dispose()


def test_payload_grows_with_page_size_not_with_history(
    repository: ProductRepository,
) -> None:
    _build_library(repository, reviewed_visits=20, needs_review_visits=80)

    small = repository.review_queue_page(_animals(page_size=5))
    large = repository.review_queue_page(_animals(page_size=50))

    small_bytes = len(small.model_dump_json())
    large_bytes = len(large.model_dump_json())
    assert large_bytes > small_bytes * 5
    # And the bounded page is a small fraction of the whole queue.
    whole = repository.review_queue_items(include_reviewed=True)
    whole_bytes = sum(len(item.model_dump_json()) for item in whole)
    assert small_bytes < whole_bytes / 5


def test_summary_returns_counts_without_any_items(
    repository: ProductRepository,
) -> None:
    _build_library(
        repository,
        reviewed_visits=12,
        needs_review_visits=30,
        second_stream_needs_review=7,
    )

    statements, summary = _count_statements(repository, repository.review_queue_summary)

    assert summary.total_items == 49
    assert summary.pending_review_count == 37
    assert summary.tab_counts.animals == 37
    assert summary.tab_counts.reviewed == 12
    assert summary.needs_review_by_stream == {STREAM_ID: 30, SECOND_STREAM_ID: 7}
    # No review cards, and no per-item cascade behind them.
    assert statements < 60, statements
    assert len(summary.model_dump_json()) < 1024


# --- tabs, filters, counts -------------------------------------------------


def test_tab_counts_and_scoping_match_the_accepted_tab_definitions(
    repository: ProductRepository,
) -> None:
    with repository.session_factory() as session:
        with session.begin():
            _add_streams(session)
            # An animal candidate, a person candidate, an unchecked item, a
            # reviewed item: one per tab the page offers.
            _add_visit(session, index=0, status=ReviewStatus.needs_review.value)
            _add_visit(
                session,
                index=1,
                status=ReviewStatus.needs_review.value,
                subject_label="person",
            )
            _add_visit(
                session,
                index=2,
                status=ReviewStatus.needs_review.value,
                event_type="wildlife_visit",
            )
            _add_visit(session, index=3, status=ReviewStatus.reviewed.value)

    page = repository.review_queue_page(_animals())
    assert page.tab_counts.animals == 1
    assert page.tab_counts.other_activity == 1
    assert page.tab_counts.unchecked == 1
    assert page.tab_counts.reviewed == 1
    assert page.pending_review_count == 3
    assert [item.visit_id for item in page.items] == ["visit-0000"]

    other = repository.review_queue_page(
        ReviewQueuePageRequest(tab=ReviewQueueProductTab.other_activity)
    )
    assert [item.visit_id for item in other.items] == ["visit-0001"]

    unchecked = repository.review_queue_page(
        ReviewQueuePageRequest(tab=ReviewQueueProductTab.unchecked)
    )
    assert [item.visit_id for item in unchecked.items] == ["visit-0002"]


def test_reviewed_tab_is_served_lazily_and_ignores_the_status_control(
    repository: ProductRepository,
) -> None:
    """Everyday Product / Discovery UX Closure v1's accepted behaviour.

    The Reviewed tab's own definition already fully determines review
    status, so the separate Status control (which defaults to "unreviewed")
    must not AND into an unsatisfiable condition and empty the tab.
    """

    _build_library(repository, reviewed_visits=40, needs_review_visits=6)

    # The default view does not carry reviewed history at all ...
    default_view = repository.review_queue_page(_animals(page_size=25))
    assert all(
        item.review_status is ReviewStatus.needs_review for item in default_view.items
    )
    assert default_view.tab_counts.reviewed == 40

    # ... and the Reviewed tab serves it a bounded page at a time.
    reviewed = repository.review_queue_page(
        ReviewQueuePageRequest(
            tab=ReviewQueueProductTab.reviewed,
            status=ReviewQueueStatusFilter.unreviewed,
            page_size=25,
        )
    )
    assert reviewed.matching_items == 40
    assert len(reviewed.items) == 25
    assert all(item.review_status is ReviewStatus.reviewed for item in reviewed.items)


def test_legacy_tab_only_matches_once_the_user_asks_to_see_it(
    repository: ProductRepository,
) -> None:
    _build_library(repository, reviewed_visits=0, needs_review_visits=2)
    # The seeded demo Source's own activity is the legacy/sample material,
    # and it is excluded from the visible queue entirely.
    hidden = repository.review_queue_page(
        ReviewQueuePageRequest(tab=ReviewQueueProductTab.legacy_activity)
    )
    assert hidden.items == []

    with repository.session_factory() as session:
        with session.begin():
            _add_visit(
                session,
                index=90,
                status=ReviewStatus.needs_review.value,
                event_type="wildlife_visit",
                with_motion_evidence=True,
            )

    off = repository.review_queue_page(
        ReviewQueuePageRequest(
            tab=ReviewQueueProductTab.legacy_activity,
            show_legacy_and_test_activity=False,
        )
    )
    on = repository.review_queue_page(
        ReviewQueuePageRequest(
            tab=ReviewQueueProductTab.legacy_activity,
            show_legacy_and_test_activity=True,
        )
    )
    assert off.items == []
    assert [item.visit_id for item in on.items] == ["visit-0090"]
    # And the legacy count only joins `pendingReviewCount` when offered.
    assert on.pending_review_count == off.pending_review_count + 1


def test_triage_counts_and_filter(repository: ProductRepository) -> None:
    _build_library(repository, reviewed_visits=0, needs_review_visits=3)
    with repository.session_factory() as session:
        with session.begin():
            _add_visit(
                session,
                index=50,
                status=ReviewStatus.needs_review.value,
                species_guess="false_positive",
            )

    page = repository.review_queue_page(_animals())
    assert page.triage_counts.all == page.total_items
    assert page.triage_counts.false_positives == 1
    # With no detection proposals and no detection runs, every other item is
    # "not checked" -- exactly what the client computed.
    assert page.triage_counts.not_analyzed == page.total_items - 1

    filtered = repository.review_queue_page(
        _animals(triage=ReviewQueueTriageFilter.false_positives)
    )
    assert [item.visit_id for item in filtered.items] == ["visit-0050"]
    # A filter narrows `matching_items`; it never changes the tab totals.
    assert filtered.tab_counts.animals == page.tab_counts.animals
    assert filtered.matching_items == 1


def test_source_stream_facet_counts_the_whole_queue(
    repository: ProductRepository,
) -> None:
    _build_library(
        repository,
        reviewed_visits=4,
        needs_review_visits=6,
        second_stream_needs_review=3,
    )

    page = repository.review_queue_page(_animals())
    options = {option.value: option for option in page.source_stream_options}

    assert options["all"].count == page.total_items
    assert options[f"stream:{STREAM_ID}"].count == 10
    assert options[f"stream:{SECOND_STREAM_ID}"].count == 3
    assert options[f"stream:{STREAM_ID}"].label == "Stream Feeder"
    assert options[f"source:{SOURCE_ID}"].count == 13

    scoped = repository.review_queue_page(
        _animals(source_stream=f"stream:{SECOND_STREAM_ID}")
    )
    assert scoped.matching_items == 3
    assert {item.stream_id for item in scoped.items} == {SECOND_STREAM_ID}


def test_search_matches_the_same_text_the_page_searched(
    repository: ProductRepository,
) -> None:
    _build_library(repository, reviewed_visits=0, needs_review_visits=4)
    with repository.session_factory() as session:
        with session.begin():
            _add_visit(
                session,
                index=60,
                status=ReviewStatus.needs_review.value,
                species_guess="Blue Jay",
            )

    by_species = repository.review_queue_page(_animals(search="blue jay"))
    assert [item.visit_id for item in by_species.items] == ["visit-0060"]

    by_id = repository.review_queue_page(_animals(search="visit-0002"))
    assert [item.visit_id for item in by_id.items] == ["visit-0002"]

    by_stream_name = repository.review_queue_page(_animals(search="feeder"))
    assert by_stream_name.matching_items == 5

    nothing = repository.review_queue_page(_animals(search="no-such-thing"))
    assert nothing.items == []
    assert nothing.matching_items == 0
    # Counts are queue-wide, so they survive a search that matches nothing.
    assert nothing.tab_counts.animals == 5


def test_stream_scoping_serves_the_streams_surfaces(
    repository: ProductRepository,
) -> None:
    _build_library(
        repository,
        reviewed_visits=2,
        needs_review_visits=9,
        second_stream_needs_review=4,
    )

    page = repository.review_queue_page(
        ReviewQueuePageRequest(
            tab=ReviewQueueProductTab.all,
            status=ReviewQueueStatusFilter.unreviewed,
            stream_id=SECOND_STREAM_ID,
            page_size=5,
        )
    )
    assert page.matching_items == 4
    assert {item.stream_id for item in page.items} == {SECOND_STREAM_ID}


def test_sort_by_triage_is_stable_within_equal_rank(
    repository: ProductRepository,
) -> None:
    _build_library(repository, reviewed_visits=0, needs_review_visits=12)

    newest = repository.review_queue_page(_animals(page_size=50))
    triage = repository.review_queue_page(
        _animals(sort=ReviewQueueSort.triage, page_size=50)
    )
    # Every item has the same triage rank here, so a stable sort must leave
    # the queue's own newest-first order untouched.
    assert [item.id for item in triage.items] == [item.id for item in newest.items]


def test_scoped_and_skipped_targets(repository: ProductRepository) -> None:
    _build_library(repository, reviewed_visits=0, needs_review_visits=6)

    scoped = repository.review_queue_page(
        _animals(scoped_target_ids=["visit-0001", "visit-0003"])
    )
    assert {item.visit_id for item in scoped.items} == {"visit-0001", "visit-0003"}

    skipped = repository.review_queue_page(_animals(skipped_target_ids=["visit-0000"]))
    assert "visit-0000" not in {item.visit_id for item in skipped.items}
    assert skipped.matching_items == 5


def test_eligible_target_ids_are_opt_in(repository: ProductRepository) -> None:
    """"Select visible eligible" is one user action, not part of every load."""

    _build_library(repository, reviewed_visits=3, needs_review_visits=9)

    default_page = repository.review_queue_page(_animals(page_size=5))
    assert default_page.eligible_target_ids is None
    assert default_page.eligible_matching_items == 9

    on_request = repository.review_queue_page(
        _animals(page_size=5, include_eligible_target_ids=True)
    )
    assert on_request.eligible_target_ids is not None
    assert len(on_request.eligible_target_ids) == 9
    assert "visit-0003" in on_request.eligible_target_ids


def test_fast_review_targets_are_bounded_and_in_queue_order(
    repository: ProductRepository,
) -> None:
    _build_library(repository, reviewed_visits=2, needs_review_visits=260)

    page = repository.review_queue_page(_animals(page_size=25))

    assert len(page.fast_review_targets) == 200
    assert page.fast_review_stream_id == STREAM_ID
    assert [target.target_id for target in page.fast_review_targets[:25]] == [
        item.visit_id for item in page.items
    ]
    assert all(target.target_type.value == "visit" for target in page.fast_review_targets)


def test_multiple_streams_leave_fast_review_unscoped(
    repository: ProductRepository,
) -> None:
    _build_library(
        repository,
        reviewed_visits=0,
        needs_review_visits=3,
        second_stream_needs_review=3,
    )

    page = repository.review_queue_page(_animals())
    assert page.fast_review_stream_id is None


# --- demo-source semantics -------------------------------------------------


def test_demo_source_activity_is_excluded_and_a_repurposed_source_is_not(
    repository: ProductRepository,
) -> None:
    """The exact `is_demo_source` contract the product boundary already had.

    A brand-new repository seeds a demo Source with example Visits. They
    must not appear, or be counted -- and a demo Source later repurposed
    into a real camera must stop being treated as demo, which is what
    `_review_queue_product_context` decides from the provider row.
    """

    seeded = repository.review_queue_page(
        ReviewQueuePageRequest(tab=ReviewQueueProductTab.all)
    )
    assert seeded.total_items == 0
    assert seeded.items == []

    unfiltered = repository.review_queue_items(include_reviewed=True)
    assert any(item.is_demo_source for item in unfiltered)

    # The established helper for exactly this scenario: give the seeded demo
    # Source a real `camera_node` effective provider, as Guided Camera
    # Editing does when an owner repurposes it into a real camera.
    de_demo_seeded_source(repository)

    repurposed = repository.review_queue_page(
        ReviewQueuePageRequest(tab=ReviewQueueProductTab.all)
    )
    assert repurposed.total_items > 0


def test_real_activity_appears_alongside_the_seeded_demo_source(
    repository: ProductRepository,
) -> None:
    _build_library(repository, reviewed_visits=1, needs_review_visits=2)

    page = repository.review_queue_page(_animals())

    assert page.total_items == 3
    assert all(not item.is_demo_source for item in page.items)


# --- mutation behaviour ----------------------------------------------------


def test_correction_moves_the_item_and_updates_counts(
    repository: ProductRepository,
) -> None:
    _build_library(repository, reviewed_visits=0, needs_review_visits=4)

    before = repository.review_queue_page(_animals())
    assert before.tab_counts.animals == 4
    assert before.tab_counts.reviewed == 0

    target = before.items[0]
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=target.visit_id,
            label="Northern Cardinal",
            notes="Review Queue Scale Closure v1 fixture correction.",
            review_origin="human",
        )
    )

    after = repository.review_queue_page(_animals())
    assert after.tab_counts.animals == 3
    assert after.tab_counts.reviewed == 1
    assert after.matching_items == 3
    assert after.pending_review_count == 3
    assert target.visit_id not in {item.visit_id for item in after.items}

    reviewed = repository.review_queue_page(
        ReviewQueuePageRequest(tab=ReviewQueueProductTab.reviewed)
    )
    assert target.visit_id in {item.visit_id for item in reviewed.items}
    # And the shell's own counts agree with the page's.
    summary = repository.review_queue_summary()
    assert summary.pending_review_count == 3
    assert summary.tab_counts.reviewed == 1


def test_reopen_restores_the_item_to_its_pending_tab(
    repository: ProductRepository,
) -> None:
    _build_library(repository, reviewed_visits=0, needs_review_visits=3)

    target = repository.review_queue_page(_animals()).items[0]
    repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit",
            target_id=target.visit_id,
            label="Northern Cardinal",
            review_origin="human",
        )
    )
    assert repository.review_queue_page(_animals()).tab_counts.animals == 2

    # The reopen needs the item's current `review_state_token`, and it comes
    # from the bounded Reviewed page -- so this also proves a page item
    # carries the hydration a real mutation depends on.
    reviewed_page = repository.review_queue_page(
        ReviewQueuePageRequest(tab=ReviewQueueProductTab.reviewed)
    )
    reviewed_item = next(
        item for item in reviewed_page.items if item.visit_id == target.visit_id
    )
    assert reviewed_item.review_state_token
    repository.reopen_visit_review(
        target.visit_id,
        VisitReviewReopenCreate(
            expected_state_token=reviewed_item.review_state_token,
            idempotency_key="review-queue-scale-closure-reopen",
            review_origin="human",
        ),
    )

    restored = repository.review_queue_page(_animals())
    assert restored.tab_counts.animals == 3
    assert restored.tab_counts.reviewed == 0
    assert target.visit_id in {item.visit_id for item in restored.items}


# --- HTTP surface ----------------------------------------------------------


async def test_http_page_and_summary(
    client, repository: ProductRepository
) -> None:
    _build_library(
        repository,
        reviewed_visits=6,
        needs_review_visits=30,
        second_stream_needs_review=4,
    )

    response = await client.get(
        "/api/review-queue/page",
        params={"tab": "animals", "page_size": 10},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 10
    assert body["matching_items"] == 34
    assert body["total_items"] == 40
    assert body["tab_counts"]["animals"] == 34
    assert body["creates_truth"] is False

    unbounded = await client.get(
        "/api/review-queue", params={"include_reviewed": "true"}
    )
    assert unbounded.status_code == 200
    # The bounded page is a small fraction of what the page used to download.
    assert len(response.content) < len(unbounded.content) / 3

    summary = await client.get("/api/review-queue/summary")
    assert summary.status_code == 200
    assert summary.json()["needs_review_by_stream"] == {
        STREAM_ID: 30,
        SECOND_STREAM_ID: 4,
    }
    assert len(summary.content) < 1024


async def test_http_page_rejects_an_out_of_range_page_size(client) -> None:
    response = await client.get("/api/review-queue/page", params={"page_size": 5000})
    assert response.status_code == 422
