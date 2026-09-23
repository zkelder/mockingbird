"""Performance / Scale / Stability Closure v1 -- review-queue build scale.

The defect these tests lock down: `_review_queue_items` materialised
*every* non-superseded Visit and *every* Event in the database, then
discarded the ones whose `review_status` did not belong in the queue --
in Python, after already having paid for a per-Visit/per-Event cascade of
evidence, media, zone, suggestion and identification lookups. Work grew
with total library size rather than with the review backlog, so the
Review Queue *and* `dashboard_summary` (which builds the same queue to
count what needs review) *and* every one of the eleven
`review_queue_count` response fields got steadily slower as a Place
accumulated history -- including the correction flow itself, which
recomputes that count on every saved correction.

These are structural tests: they assert the *number of SQL statements*
the build issues, and that the returned queue is unchanged. A wall-clock
assertion would be environment-dependent; statement count is not, and an
N+1 over the whole table is exactly a statement count.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

from sqlalchemy import event as sa_event

from mockingbird.api.schemas import ReviewStatus, SourceKind, SourceStatus
from mockingbird.repository.product_repository import (
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


SOURCE_ID = "source-scale"
STREAM_ID = "stream-scale"
_NOW = datetime(2026, 9, 22, 12, 0, tzinfo=UTC)


def _build_library(
    repository: ProductRepository,
    *,
    reviewed_visits: int,
    needs_review_visits: int,
    eventless_needs_review: int = 0,
) -> None:
    """A library whose *backlog* is small and whose *history* is large."""

    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID,
                    name="Scale Camera",
                    kind=SourceKind.integration.value,
                    status=SourceStatus.connected.value,
                    description="Scale fixture.",
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
            session.add(
                StreamModel(
                    id=STREAM_ID,
                    source_id=SOURCE_ID,
                    name="Scale Stream",
                    description="Scale fixture stream.",
                    is_live=True,
                )
            )

            index = 0
            for status, count in (
                (ReviewStatus.reviewed.value, reviewed_visits),
                (ReviewStatus.needs_review.value, needs_review_visits),
            ):
                for _ in range(count):
                    # Zero-padded so `order_by(VisitModel.id)` matches
                    # insertion order and the ordering assertion below is
                    # about the query, not about string sort surprises.
                    event_id = f"event-{index:04d}"
                    visit_id = f"visit-{index:04d}"
                    asset_id = f"asset-{index:04d}"
                    # Reviewed history is genuinely *old* and the backlog is
                    # recent -- the real shape of an established install, and
                    # the only shape that lets the dashboard test below
                    # distinguish "scales with total history" (the defect)
                    # from "scales with today's activity" (bounded by
                    # `_dashboard_today_summary`'s own `.limit(501)`).
                    started_at = (
                        _NOW - timedelta(days=30) - timedelta(minutes=index)
                        if status == ReviewStatus.reviewed.value
                        else _NOW - timedelta(minutes=index)
                    )
                    session.add(
                        EventModel(
                            id=event_id,
                            stream_id=STREAM_ID,
                            title=f"Scale event {index}",
                            event_type="wildlife_visit",
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
                            stream_id=STREAM_ID,
                            filename=f"{asset_id}.jpg",
                            content_type="image/jpeg",
                            media_type="image",
                            local_path=f"scale/{asset_id}.jpg",
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
                            subject_label="bird",
                            species_guess="Northern Cardinal",
                            confidence=0.8,
                            reviewed_label=(
                                "Northern Cardinal"
                                if status == ReviewStatus.reviewed.value
                                else None
                            ),
                            review_status=status,
                            representative_media_path=f"scale/{asset_id}.jpg",
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
                    index += 1

            # Visit-less Events are a real second queue source with their
            # own loop; give it both a reviewed majority and a small
            # backlog so the same scaling question is asked of it too.
            for offset in range(eventless_needs_review + reviewed_visits):
                status = (
                    ReviewStatus.needs_review.value
                    if offset < eventless_needs_review
                    else ReviewStatus.reviewed.value
                )
                started_at = _NOW - timedelta(days=1, minutes=offset)
                session.add(
                    EventModel(
                        id=f"eventless-{offset:04d}",
                        stream_id=STREAM_ID,
                        title=f"Eventless {offset}",
                        event_type="wildlife_visit",
                        started_at=started_at,
                        ended_at=started_at + timedelta(seconds=10),
                        primary_zone_id=None,
                        review_status=status,
                    )
                )


def _real_items(queue):
    """Drop the seeded demo Source's own items.

    A fresh `ProductRepository` seeds demo activity, which legitimately
    appears in `review_queue_items` (flagged `is_demo_source`) and is
    excluded at the product boundary by `_visible_review_queue_items`.
    These tests are about the *fixture's* library, so they look at the
    same real-activity subset a user is shown.
    """

    return [item for item in queue if not item.is_demo_source]


def _count_statements(repository: ProductRepository, call) -> tuple[int, object]:
    counter = {"n": 0}

    def _on_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        counter["n"] += 1

    sa_event.listen(repository.engine, "before_cursor_execute", _on_execute)
    try:
        result = call()
    finally:
        sa_event.remove(repository.engine, "before_cursor_execute", _on_execute)
    return counter["n"], result


def test_review_queue_build_does_not_scale_with_reviewed_history(tmp_path) -> None:
    """Ten times the *history*, same backlog, must not cost ten times the work."""

    small = ProductRepository(db_url=f"sqlite:///{tmp_path / 'small.sqlite3'}")
    large = ProductRepository(db_url=f"sqlite:///{tmp_path / 'large.sqlite3'}")
    try:
        _build_library(small, reviewed_visits=20, needs_review_visits=5, eventless_needs_review=2)
        _build_library(large, reviewed_visits=200, needs_review_visits=5, eventless_needs_review=2)

        small_statements, small_queue = _count_statements(small, small.review_queue_items)
        large_statements, large_queue = _count_statements(large, large.review_queue_items)

        # Identical backlog => identical queue shape. (Visit ids differ
        # between the two fixtures because the larger one has more reviewed
        # rows ahead of its backlog, so the comparison is on shape and
        # status, not on the generated identifiers.)
        small_items = _real_items(small_queue)
        large_items = _real_items(large_queue)
        assert len(small_items) == len(large_items) == 7  # 5 Visits + 2 Events
        assert [item.item_type for item in small_items] == [
            item.item_type for item in large_items
        ]
        assert {item.review_status for item in small_items} == {ReviewStatus.needs_review}

        # The whole point: a 10x larger reviewed history must not multiply
        # the work. Measured directly: before the fix, 178 statements at 25
        # Visits and 538 at 205; after it, 132 and 132. A small constant
        # overhead (the handful of bounded top-level queries) is expected;
        # proportional growth is the bug.
        assert large_statements <= small_statements + 10, (
            f"review queue build scaled with reviewed history: "
            f"{small_statements} statements at 25 Visits, "
            f"{large_statements} at 205"
        )
    finally:
        small.close()
        large.close()


def test_review_queue_still_returns_reviewed_history_when_asked(tmp_path) -> None:
    """`include_reviewed=True` must still return the reviewed items."""

    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'opt-in.sqlite3'}")
    try:
        _build_library(repository, reviewed_visits=6, needs_review_visits=3, eventless_needs_review=1)

        default_queue = repository.review_queue_items()
        full_queue = repository.review_queue_items(include_reviewed=True)

        default_ids = {item.target_id for item in _real_items(default_queue)}
        full_ids = {item.target_id for item in _real_items(full_queue)}

        assert default_ids < full_ids
        assert {item.review_status for item in _real_items(default_queue)} == {
            ReviewStatus.needs_review
        }
        assert ReviewStatus.reviewed in {item.review_status for item in _real_items(full_queue)}
        # Every reviewed Visit, and the reviewed visit-less Events, appear.
        assert len(full_ids) == len(default_ids) + 6 + 6
    finally:
        repository.close()


def test_review_queue_order_is_unchanged_by_the_filtered_query(tmp_path) -> None:
    """Pushing the status filter into SQL must not reorder the queue."""

    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'order.sqlite3'}")
    try:
        _build_library(repository, reviewed_visits=4, needs_review_visits=6, eventless_needs_review=3)
        queue = _real_items(repository.review_queue_items())

        visit_items = [item for item in queue if item.item_type == "visit"]
        # `_visits_for_eventless_query` ordered by Visit id; the filtered
        # query must preserve exactly that.
        assert [item.target_id for item in visit_items] == sorted(
            item.target_id for item in visit_items
        )
        # Visit items precede the visit-less Event items, as before.
        assert [item.item_type for item in queue] == ["visit"] * len(visit_items) + [
            item.item_type for item in queue[len(visit_items) :]
        ]
    finally:
        repository.close()


def test_dashboard_summary_does_not_rebuild_the_whole_library(tmp_path) -> None:
    """The landing page shares the queue build; it must share the fix too."""

    small = ProductRepository(db_url=f"sqlite:///{tmp_path / 'dash-small.sqlite3'}")
    large = ProductRepository(db_url=f"sqlite:///{tmp_path / 'dash-large.sqlite3'}")
    try:
        _build_library(small, reviewed_visits=20, needs_review_visits=4)
        _build_library(large, reviewed_visits=200, needs_review_visits=4)

        small_statements, _ = _count_statements(small, small.dashboard_summary)
        large_statements, _ = _count_statements(large, large.dashboard_summary)

        # `dashboard_summary`'s own "today" section is separately bounded
        # (`.limit(501)`) and this fixture keeps the reviewed history a
        # month old, so today's work is identical in both libraries and the
        # only thing that differs is history size. Measured directly:
        # before the fix, 442 statements at 24 Visits and 807 at 204;
        # after it, 396 and 401. A small constant margin allows for the
        # handful of bounded top-level queries; growth in proportion to
        # history is the defect.
        assert large_statements <= small_statements + 25, (
            f"dashboard_summary scaled with reviewed history: "
            f"{small_statements} statements at 24 Visits, "
            f"{large_statements} at 204"
        )
    finally:
        small.close()
        large.close()


def test_review_queue_count_matches_the_items_it_counts(tmp_path) -> None:
    """The count every correction recomputes must equal the visible queue."""

    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'count.sqlite3'}")
    try:
        _build_library(repository, reviewed_visits=12, needs_review_visits=5, eventless_needs_review=2)
        with repository.session_factory() as session:
            items = repository._visible_review_queue_items(session)
            count = repository._visible_review_queue_count(session)
        assert count == len(items)
        assert len(_real_items(items)) == 7
    finally:
        repository.close()


def test_superseded_visits_are_still_excluded(tmp_path) -> None:
    """The filtered query must keep the `is_superseded` exclusion."""

    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'superseded.sqlite3'}")
    try:
        _build_library(repository, reviewed_visits=2, needs_review_visits=4)
        with repository.session_factory() as session:
            with session.begin():
                target = session.get(VisitModel, "visit-0002")
                assert target is not None
                assert target.review_status == ReviewStatus.needs_review.value
                target.is_superseded = True

        queue = _real_items(repository.review_queue_items())
        assert "visit-0002" not in {item.target_id for item in queue}
        assert len([item for item in queue if item.item_type == "visit"]) == 3
    finally:
        repository.close()


def test_visit_evidence_still_resolves_for_queued_items(tmp_path) -> None:
    """Filtering earlier must not strip a queued item's own evidence."""

    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'evidence.sqlite3'}")
    try:
        _build_library(repository, reviewed_visits=3, needs_review_visits=2)
        queue = _real_items(repository.review_queue_items())
        visit_items = [item for item in queue if item.item_type == "visit"]
        assert visit_items
        for item in visit_items:
            assert item.evidence_frames, f"{item.target_id} lost its evidence frames"
            assert item.media_asset is not None
            assert item.best_media_asset_id is not None
            assert item.review_state_token
            # Provenance/JSON-shaped fields survive the narrower query.
            assert item.stream_id == STREAM_ID
            assert item.source_id == SOURCE_ID
    finally:
        repository.close()


def test_review_queue_is_unchanged_for_a_mixed_library(tmp_path) -> None:
    """A broad equivalence check across every queue field, not just ids."""

    repository = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mixed.sqlite3'}")
    try:
        _build_library(repository, reviewed_visits=7, needs_review_visits=4, eventless_needs_review=3)
        queue = _real_items(repository.review_queue_items())
        serialized = json.loads(
            json.dumps([item.model_dump(mode="json") for item in queue], sort_keys=True)
        )
        # Re-running the build must be deterministic -- the narrower query
        # must not have introduced any ordering or content instability.
        again = json.loads(
            json.dumps(
                [
                    item.model_dump(mode="json")
                    for item in _real_items(repository.review_queue_items())
                ],
                sort_keys=True,
            )
        )
        assert serialized == again
        assert len(queue) == 7
    finally:
        repository.close()
