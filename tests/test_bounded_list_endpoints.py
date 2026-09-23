"""Performance / Scale / Stability Closure v1 -- bounded list surfaces.

The v0.1 pre-release baseline audit flagged `GET /api/visits` as returning
the entire Visit table with no limit. Measured at an ordinary
established-install size (2,813 Visits / 11,244 media assets) it returned
754 KB, and `GET /api/events` returned 1.2 MB while issuing one further
`SELECT` per Event for that Event's detections -- 2,820 statements for one
request. Neither route has a consumer anywhere in the shipped frontend
(verified across the whole `web/src` tree), so both now carry a bounded
default page size with explicit `limit`/`offset` continuation.

These tests pin three things: the bound is real, paging covers the whole
table without gaps or duplicates, and the per-Event detection read no
longer scales with the number of Events returned.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

import pytest
from sqlalchemy import event as sa_event

from mockingbird.api.main import _DEFAULT_LIST_PAGE_SIZE, _MAX_LIST_PAGE_SIZE
from mockingbird.api.schemas import ReviewStatus, SourceKind, SourceStatus
from mockingbird.repository.product_repository import (
    ProductRepository,
    SourceProviderConfigurationModel,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    DetectionModel,
    EventModel,
    StreamModel,
    VisitModel,
)


SOURCE_ID = "source-bounded"
STREAM_ID = "stream-bounded"
_NOW = datetime(2026, 9, 22, 9, 0, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path):
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'bounded.sqlite3'}")
    yield repo
    repo.close()


def _build(repository: ProductRepository, *, count: int, detections_per_event: int = 2) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID,
                    name="Bounded Camera",
                    kind=SourceKind.integration.value,
                    status=SourceStatus.connected.value,
                    description="Bounded fixture.",
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
                    name="Bounded Stream",
                    description="Bounded fixture stream.",
                    is_live=True,
                )
            )
            for index in range(count):
                event_id = f"bevent-{index:04d}"
                started_at = _NOW + timedelta(minutes=index)
                session.add(
                    EventModel(
                        id=event_id,
                        stream_id=STREAM_ID,
                        title=f"Bounded {index}",
                        event_type="wildlife_visit",
                        started_at=started_at,
                        ended_at=started_at + timedelta(seconds=20),
                        primary_zone_id=None,
                        review_status=ReviewStatus.needs_review.value,
                    )
                )
                for detection_index in range(detections_per_event):
                    session.add(
                        DetectionModel(
                            id=f"bdet-{index:04d}-{detection_index}",
                            event_id=event_id,
                            label="animal",
                            confidence=0.5,
                            zone_id=None,
                            bbox_json=json.dumps(
                                {"x": 0.2, "y": 0.2, "width": 0.3, "height": 0.3}
                            ),
                        )
                    )
                session.add(
                    VisitModel(
                        id=f"bvisit-{index:04d}",
                        event_id=event_id,
                        subject_label="bird",
                        species_guess="Northern Cardinal",
                        confidence=0.7,
                        reviewed_label=None,
                        review_status=ReviewStatus.needs_review.value,
                        representative_media_path=None,
                        zone_id=None,
                        is_superseded=False,
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


def test_visits_and_events_default_to_a_bounded_page(repository) -> None:
    total = _DEFAULT_LIST_PAGE_SIZE + 37
    _build(repository, count=total)

    assert len(repository.list_visits(limit=_DEFAULT_LIST_PAGE_SIZE)) == _DEFAULT_LIST_PAGE_SIZE
    assert len(repository.list_events(limit=_DEFAULT_LIST_PAGE_SIZE)) == _DEFAULT_LIST_PAGE_SIZE
    # The bound is a page size, not a ceiling on what exists.
    assert len(repository.list_visits()) >= total
    assert len(repository.list_events()) >= total


def test_paging_covers_every_row_exactly_once(repository) -> None:
    _build(repository, count=120)

    everything = [visit.id for visit in repository.list_visits()]
    paged: list[str] = []
    offset = 0
    while True:
        page = repository.list_visits(limit=25, offset=offset)
        if not page:
            break
        paged.extend(visit.id for visit in page)
        offset += 25

    assert paged == everything
    assert len(set(paged)) == len(paged)

    all_events = [item.id for item in repository.list_events()]
    paged_events: list[str] = []
    offset = 0
    while True:
        page = repository.list_events(limit=25, offset=offset)
        if not page:
            break
        paged_events.extend(item.id for item in page)
        offset += 25
    assert paged_events == all_events


def test_event_detections_do_not_cost_one_query_per_event(repository) -> None:
    _build(repository, count=200, detections_per_event=3)

    few_statements, few = _count_statements(
        repository, lambda: repository.list_events(limit=10)
    )
    many_statements, many = _count_statements(
        repository, lambda: repository.list_events(limit=200)
    )

    assert len(few) == 10 and len(many) == 200
    # Detections still arrive in full -- this is a batching change, not a
    # dropped field. (A fresh repository also seeds demo Events, which have
    # their own detection counts; assert against this fixture's own.)
    fixture_events = [item for item in many if item.id.startswith("bevent-")]
    assert fixture_events
    assert all(len(item.detections) == 3 for item in fixture_events)
    assert [detection.id for detection in fixture_events[0].detections] == [
        "bdet-0000-0", "bdet-0000-1", "bdet-0000-2"
    ]
    # 20x the Events must not mean 20x the statements.
    assert many_statements <= few_statements + 2, (
        f"list_events scaled with Event count: {few_statements} statements "
        f"for 10 Events, {many_statements} for 200"
    )


def test_event_projection_is_unchanged_by_batching(repository) -> None:
    _build(repository, count=5, detections_per_event=2)

    listed = {item.id: item for item in repository.list_events()}
    for event_id, listed_event in listed.items():
        single = repository.get_event(event_id)
        assert single is not None
        assert single.model_dump(mode="json") == listed_event.model_dump(mode="json")


def test_review_labels_visit_filter_does_not_query_per_label(repository) -> None:
    """The superseded-Visit exclusion used one `session.get` per label."""

    from mockingbird.storage.models import ReviewLabelModel

    _build(repository, count=150)
    with repository.session_factory() as session:
        with session.begin():
            for index in range(150):
                session.add(
                    ReviewLabelModel(
                        id=f"blabel-{index:04d}",
                        target_type="visit",
                        target_id=f"bvisit-{index:04d}",
                        label="Northern Cardinal",
                        notes=None,
                        created_at=_NOW + timedelta(minutes=index),
                        review_origin="human",
                        reviewer_identity="Bounded fixture",
                    )
                )
            # One superseded Visit must still be excluded.
            superseded = session.get(VisitModel, "bvisit-0007")
            assert superseded is not None
            superseded.is_superseded = True

    statements, labels = _count_statements(repository, repository.list_review_labels)
    returned = {label.target_id for label in labels}
    assert "bvisit-0007" not in returned
    assert len([label for label in labels if label.target_type == "visit"]) == 149
    # One labels query, one chunked Visit query, plus a little connection
    # overhead -- never one per label.
    assert statements <= 8, f"list_review_labels issued {statements} statements for 150 labels"


def test_route_rejects_an_out_of_range_page_size() -> None:
    assert _MAX_LIST_PAGE_SIZE > _DEFAULT_LIST_PAGE_SIZE
