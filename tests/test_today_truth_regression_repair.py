"""Today Truth Regression Repair v1 -- the preload lookup contract.

The defect these tests lock down: Review Queue Scale Closure v1's bulk
`MotionEvidence` preload answered with an authoritative `None` for any
Visit/Event it had never fetched. `_read_only_build_cache` is shared by
nested builds, and `dashboard_summary` deliberately runs the review-queue
build and *then* Today inside one of them -- so Today's reviewed/confirmed
Visits, which are not queue members, were told they had no motion
evidence. `_review_queue_product_context` then classified them
`detector_class != "animal"` and Today's confirmed-wildlife counts
collapsed toward zero. Confirming wildlife made that wildlife disappear
from Today.

The contract asserted here is one sentence: **a cache answer must equal
the answer the original database query would have given.** Every case
below is therefore checked twice -- once with the preload active and once
with it absent -- and the two answers must agree. That is stronger than
asserting a particular value, because it cannot drift away from the query
it is standing in for.

These tests exercise `_motion_evidence_for_review_queue_item` directly
rather than through a product surface, because the three distinguishable
states (outside coverage / covered with no rows / covered with rows) are
not separately observable from a response body.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json

from sqlalchemy import event as sa_event, func, select

from mockingbird.repository.product_repository import (
    MotionEvidenceModel,
    ProductRepository,
    _read_only_build_cache,
)
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    ReviewLabelModel,
    StreamModel,
    VisitModel,
)


SOURCE_ID = "source-preload"
STREAM_ID = "stream-preload"
_NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def _repository(tmp_path, name: str = "preload.sqlite3") -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / name}",
        media_root=tmp_path / "media",
    )
    with repository.session_factory() as session:
        with session.begin():
            demo = session.get(CameraSourceModel, "source-backyard-demo")
            assert demo is not None
            demo.status = "archived"
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID,
                    name="Preload camera",
                    kind="integration",
                    status="connected",
                    description="Preload coverage fixture.",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID,
                    source_id=SOURCE_ID,
                    name="Preload stream",
                    description="Preload coverage fixture.",
                    is_live=True,
                )
            )
    return repository


def _detector_scoring(detector_class: str = "animal") -> str:
    return json.dumps(
        {
            "detector_evidence": json.dumps(
                {
                    "current_track": {
                        "track_generation_id": "track-preload",
                        "class": detector_class,
                        "score": 0.8,
                    }
                }
            )
        }
    )


def _add_visit(
    repository: ProductRepository,
    *,
    visit_id: str,
    reviewed_label: str | None = None,
    observed_at: datetime = _NOW,
    with_evidence: bool = True,
    evidence_media: bool = True,
    detector_class: str = "animal",
) -> str:
    """One Event + Visit (+ media, review label, MotionEvidence)."""

    event_id = f"event-{visit_id}"
    media_id = f"media-{visit_id}"
    review_status = "reviewed" if reviewed_label is not None else "needs_review"
    media_path = repository.media_root / f"{visit_id}.jpg"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_id,
                    source_id=SOURCE_ID,
                    stream_id=STREAM_ID,
                    filename=f"{visit_id}.jpg",
                    content_type="image/jpeg",
                    media_type="image",
                    local_path=str(media_path),
                    original_filename=f"{visit_id}.jpg",
                    file_size_bytes=64,
                    created_at=observed_at,
                    captured_at=observed_at,
                )
            )
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=STREAM_ID,
                    title=f"Preload {visit_id}",
                    event_type="durable_monitoring_visit",
                    started_at=observed_at,
                    ended_at=observed_at + timedelta(seconds=20),
                    primary_zone_id=None,
                    review_status=review_status,
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="unknown_animal",
                    species_guess=None,
                    confidence=None,
                    reviewed_label=reviewed_label,
                    review_status=review_status,
                    representative_media_path=str(media_path),
                    zone_id=None,
                    is_superseded=False,
                )
            )
            if reviewed_label is not None:
                session.add(
                    ReviewLabelModel(
                        id=f"review-label-{visit_id}",
                        target_type="visit",
                        target_id=visit_id,
                        label=reviewed_label,
                        notes=None,
                        created_at=observed_at + timedelta(minutes=1),
                    )
                )
            if with_evidence:
                session.add(
                    _motion_evidence(
                        evidence_id=f"evidence-{visit_id}",
                        event_id=event_id,
                        visit_id=visit_id,
                        media_asset_id=media_id if evidence_media else None,
                        created_at=observed_at,
                        detector_class=detector_class,
                    )
                )
    return event_id


def _motion_evidence(
    *,
    evidence_id: str,
    event_id: str | None,
    visit_id: str | None,
    media_asset_id: str | None,
    created_at: datetime,
    detector_class: str = "animal",
) -> MotionEvidenceModel:
    return MotionEvidenceModel(
        id=evidence_id,
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        zone_id=None,
        start_frame_index=None,
        end_frame_index=None,
        best_frame_index=None,
        start_time=None,
        end_time=None,
        best_frame_time=None,
        peak_changed_ratio=0.1,
        triggered_frame_count=1,
        scoring_config_json=_detector_scoring(detector_class),
        snapshot_media_asset_id=media_asset_id,
        status="promoted",
        promoted_event_id=event_id,
        promoted_visit_id=visit_id,
        created_at=created_at,
        notes=None,
    )


def _lookup_both_ways(
    repository: ProductRepository,
    *,
    queue_visit_id: str,
    event_id: str | None,
    visit_id: str | None,
    media_asset_id: str | None = None,
) -> tuple[str | None, str | None]:
    """The same lookup with the preload active, and with no cache at all.

    `queue_visit_id` is the Visit the review-queue preload is run for, so
    the caller controls exactly what the cache covers. Returns the
    MotionEvidence id each path resolved (or `None`), which is what the
    equality contract is about.
    """

    with repository.session_factory() as session:
        with _read_only_build_cache(session) as cache:
            repository._preload_review_queue_rows(
                session,
                cache,
                include_reviewed=False,
                only_targets={("visit", queue_visit_id)},
            )
            cached = repository._motion_evidence_for_review_queue_item(
                session,
                event_id=event_id,
                visit_id=visit_id,
                media_asset_id=media_asset_id,
            )
            cached_id = cached.id if cached is not None else None

    with repository.session_factory() as session:
        uncached = repository._motion_evidence_for_review_queue_item(
            session,
            event_id=event_id,
            visit_id=visit_id,
            media_asset_id=media_asset_id,
        )
        uncached_id = uncached.id if uncached is not None else None

    return cached_id, uncached_id


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


# --- The three distinguishable states ---------------------------------------


def test_target_outside_preload_coverage_falls_through_to_the_query(tmp_path) -> None:
    """The regression itself: a Visit the preload never read.

    `queued` is the queue's only member, so the preload covers it and
    nothing else. `confirmed` is reviewed -- not a queue member -- and has
    real MotionEvidence. Before the repair the cache answered `None` for
    it; the query answers with the evidence row, and the two must agree.
    """

    repository = _repository(tmp_path)
    try:
        _add_visit(repository, visit_id="queued")
        confirmed_event = _add_visit(
            repository, visit_id="confirmed", reviewed_label="northern_cardinal"
        )

        cached_id, uncached_id = _lookup_both_ways(
            repository,
            queue_visit_id="queued",
            event_id=confirmed_event,
            visit_id="confirmed",
        )

        assert uncached_id == "evidence-confirmed"
        assert cached_id == uncached_id
    finally:
        repository.close()


def test_covered_target_with_no_evidence_answers_none_from_the_cache(tmp_path) -> None:
    """A covered Visit with genuinely no rows is still a real `None`.

    This is the half of the optimization worth keeping: the preload read
    this Visit, found nothing, and may say so without a second query.
    """

    repository = _repository(tmp_path)
    try:
        event_id = _add_visit(repository, visit_id="queued", with_evidence=False)

        cached_id, uncached_id = _lookup_both_ways(
            repository,
            queue_visit_id="queued",
            event_id=event_id,
            visit_id="queued",
        )

        assert uncached_id is None
        assert cached_id is None

        # ...and it really is served from the cache, not re-queried.
        with repository.session_factory() as session:
            with _read_only_build_cache(session) as cache:
                repository._preload_review_queue_rows(
                    session,
                    cache,
                    include_reviewed=False,
                    only_targets={("visit", "queued")},
                )
                statements, _ = _count_statements(
                    repository,
                    lambda: repository._motion_evidence_for_review_queue_item(
                        session,
                        event_id=event_id,
                        visit_id="queued",
                        media_asset_id=None,
                    ),
                )
        assert statements == 0
    finally:
        repository.close()


def test_covered_target_with_evidence_is_served_without_a_query(tmp_path) -> None:
    repository = _repository(tmp_path)
    try:
        event_id = _add_visit(repository, visit_id="queued")

        cached_id, uncached_id = _lookup_both_ways(
            repository,
            queue_visit_id="queued",
            event_id=event_id,
            visit_id="queued",
        )
        assert uncached_id == "evidence-queued"
        assert cached_id == uncached_id

        with repository.session_factory() as session:
            with _read_only_build_cache(session) as cache:
                repository._preload_review_queue_rows(
                    session,
                    cache,
                    include_reviewed=False,
                    only_targets={("visit", "queued")},
                )
                statements, _ = _count_statements(
                    repository,
                    lambda: repository._motion_evidence_for_review_queue_item(
                        session,
                        event_id=event_id,
                        visit_id="queued",
                        media_asset_id=None,
                    ),
                )
        assert statements == 0
    finally:
        repository.close()


def test_mixed_covered_visit_and_uncovered_event_falls_through(tmp_path) -> None:
    """A union predicate cannot be answered from half of it.

    The lookup's `(visit OR event)` predicate spans a covered Visit and an
    Event the preload never read, and the answer lives on the *Event*
    side. A partial answer here is a wrong answer, not a slower one.
    """

    repository = _repository(tmp_path)
    try:
        _add_visit(repository, visit_id="queued", with_evidence=False)
        other_event = _add_visit(
            repository, visit_id="other", reviewed_label="blue_jay"
        )
        # Evidence promoted to the *other* Event only, so the covered
        # Visit side contributes nothing.
        with repository.session_factory() as session:
            with session.begin():
                session.add(
                    _motion_evidence(
                        evidence_id="evidence-cross",
                        event_id=other_event,
                        visit_id=None,
                        media_asset_id=None,
                        created_at=_NOW + timedelta(minutes=5),
                    )
                )

        cached_id, uncached_id = _lookup_both_ways(
            repository,
            queue_visit_id="queued",
            event_id=other_event,
            visit_id="queued",
        )

        assert uncached_id == "evidence-cross"
        assert cached_id == uncached_id
    finally:
        repository.close()


def test_uncovered_event_only_lookup_falls_through(tmp_path) -> None:
    """The visit-less Event lane: `visit_id=None`, Event outside coverage."""

    repository = _repository(tmp_path)
    try:
        _add_visit(repository, visit_id="queued")
        with repository.session_factory() as session:
            with session.begin():
                session.add(
                    EventModel(
                        id="eventless",
                        stream_id=STREAM_ID,
                        title="Visit-less activity",
                        event_type="durable_monitoring_visit",
                        started_at=_NOW,
                        ended_at=_NOW + timedelta(seconds=10),
                        primary_zone_id=None,
                        review_status="needs_review",
                    )
                )
                session.add(
                    _motion_evidence(
                        evidence_id="evidence-eventless",
                        event_id="eventless",
                        visit_id=None,
                        media_asset_id=None,
                        created_at=_NOW,
                    )
                )

        cached_id, uncached_id = _lookup_both_ways(
            repository,
            queue_visit_id="queued",
            event_id="eventless",
            visit_id=None,
        )

        assert uncached_id == "evidence-eventless"
        assert cached_id == uncached_id
    finally:
        repository.close()


# --- Preserved behaviour: media filter, ordering, dedup ---------------------


def test_media_asset_filter_is_preserved_on_both_paths(tmp_path) -> None:
    """`media_asset_id` narrows the union, cached and uncached alike."""

    repository = _repository(tmp_path)
    try:
        event_id = _add_visit(repository, visit_id="queued")
        with repository.session_factory() as session:
            with session.begin():
                session.add(
                    MediaAssetModel(
                        id="media-second",
                        source_id=SOURCE_ID,
                        stream_id=STREAM_ID,
                        filename="second.jpg",
                        content_type="image/jpeg",
                        media_type="image",
                        local_path=str(repository.media_root / "second.jpg"),
                        original_filename="second.jpg",
                        file_size_bytes=64,
                        created_at=_NOW,
                        captured_at=_NOW,
                    )
                )
                # Newer, but attached to a different media asset: the
                # filtered lookup must not pick it.
                session.add(
                    _motion_evidence(
                        evidence_id="evidence-second",
                        event_id=event_id,
                        visit_id="queued",
                        media_asset_id="media-second",
                        created_at=_NOW + timedelta(minutes=10),
                    )
                )

        for media_asset_id, expected in (
            ("media-queued", "evidence-queued"),
            ("media-second", "evidence-second"),
            ("media-absent", None),
        ):
            cached_id, uncached_id = _lookup_both_ways(
                repository,
                queue_visit_id="queued",
                event_id=event_id,
                visit_id="queued",
                media_asset_id=media_asset_id,
            )
            assert uncached_id == expected, media_asset_id
            assert cached_id == uncached_id, media_asset_id
    finally:
        repository.close()


def test_newest_first_ordering_including_created_at_ties(tmp_path) -> None:
    """Newest by `created_at`, then highest `id` -- the query's own ORDER BY."""

    repository = _repository(tmp_path)
    try:
        event_id = _add_visit(repository, visit_id="queued", with_evidence=False)
        with repository.session_factory() as session:
            with session.begin():
                session.add(
                    _motion_evidence(
                        evidence_id="evidence-older",
                        event_id=event_id,
                        visit_id="queued",
                        media_asset_id=None,
                        created_at=_NOW - timedelta(hours=1),
                    )
                )
                # Two rows sharing one `created_at`: the tie is broken by
                # `id DESC`, so `evidence-tie-b` wins over `evidence-tie-a`.
                for suffix in ("a", "b"):
                    session.add(
                        _motion_evidence(
                            evidence_id=f"evidence-tie-{suffix}",
                            event_id=event_id,
                            visit_id="queued",
                            media_asset_id=None,
                            created_at=_NOW,
                        )
                    )

        cached_id, uncached_id = _lookup_both_ways(
            repository,
            queue_visit_id="queued",
            event_id=event_id,
            visit_id="queued",
        )
        assert uncached_id == "evidence-tie-b"
        assert cached_id == uncached_id
    finally:
        repository.close()


def test_a_row_promoted_to_both_visit_and_event_is_counted_once(tmp_path) -> None:
    """The union dedups, so a shared row cannot outrank a genuinely newer one."""

    repository = _repository(tmp_path)
    try:
        event_id = _add_visit(repository, visit_id="queued")
        with repository.session_factory() as session:
            with session.begin():
                session.add(
                    _motion_evidence(
                        evidence_id="evidence-newer-event-only",
                        event_id=event_id,
                        visit_id=None,
                        media_asset_id=None,
                        created_at=_NOW + timedelta(minutes=1),
                    )
                )

        cached_id, uncached_id = _lookup_both_ways(
            repository,
            queue_visit_id="queued",
            event_id=event_id,
            visit_id="queued",
        )
        assert uncached_id == "evidence-newer-event-only"
        assert cached_id == uncached_id
    finally:
        repository.close()


# --- Nested cache lifetime ---------------------------------------------------


def test_a_nested_build_cannot_make_the_outer_build_answer_wrongly(tmp_path) -> None:
    """Nested builds share the outermost cache and replace its preload.

    The inner build narrows coverage to one Visit. Afterwards the outer
    build's other Visits are outside coverage, and must fall through to
    the query rather than inherit the inner build's answer.
    """

    repository = _repository(tmp_path)
    try:
        first_event = _add_visit(repository, visit_id="first")
        second_event = _add_visit(repository, visit_id="second")

        with repository.session_factory() as session:
            with _read_only_build_cache(session) as cache:
                repository._preload_review_queue_rows(
                    session, cache, include_reviewed=False
                )
                # A nested single-target build, exactly what every saved
                # correction runs (`_review_queue_item_by_target`).
                repository._review_queue_items(
                    session,
                    include_detail=False,
                    only_target=("visit", "first"),
                )
                after_nested = repository._motion_evidence_for_review_queue_item(
                    session,
                    event_id=second_event,
                    visit_id="second",
                    media_asset_id=None,
                )
        assert after_nested is not None
        assert after_nested.id == "evidence-second"
        assert first_event  # the nested build's own target, kept explicit
    finally:
        repository.close()


def test_the_preload_never_escapes_its_own_build(tmp_path) -> None:
    """Leaving the cache context removes it; a later read re-queries."""

    repository = _repository(tmp_path)
    try:
        event_id = _add_visit(repository, visit_id="queued", with_evidence=False)
        with repository.session_factory() as session:
            with _read_only_build_cache(session) as cache:
                repository._preload_review_queue_rows(
                    session, cache, include_reviewed=False
                )
            statements, evidence = _count_statements(
                repository,
                lambda: repository._motion_evidence_for_review_queue_item(
                    session,
                    event_id=event_id,
                    visit_id="queued",
                    media_asset_id=None,
                ),
            )
        assert evidence is None
        assert statements == 1
    finally:
        repository.close()


# --- Product outcome: Confirm must not erase from Today ----------------------


def test_confirmed_wildlife_stays_counted_on_today_without_duplication(
    tmp_path,
) -> None:
    """Discover -> Confirm -> Remember, across the review-to-Today transition.

    One Visit, counted by Today while it still needs review, and still
    counted -- exactly once -- after it is confirmed. The regression made
    the second half of that false.
    """

    repository = _repository(tmp_path)
    try:
        _add_visit(repository, visit_id="visitor", observed_at=_NOW)

        local_day = _NOW.date()
        before = repository.dashboard_summary(now=_NOW, local_date=local_day).today
        assert before.detector_qualified_animal_visit_count == 1

        with repository.session_factory() as session:
            with session.begin():
                visit = session.get(VisitModel, "visitor")
                assert visit is not None
                visit.reviewed_label = "northern_cardinal"
                visit.review_status = "reviewed"
                event = session.get(EventModel, "event-visitor")
                assert event is not None
                event.review_status = "reviewed"
                session.add(
                    ReviewLabelModel(
                        id="review-label-visitor",
                        target_type="visit",
                        target_id="visitor",
                        label="northern_cardinal",
                        notes=None,
                        created_at=_NOW + timedelta(minutes=1),
                    )
                )

        after = repository.dashboard_summary(now=_NOW, local_date=local_day).today

        # Confirming it must not remove it from the count...
        assert after.detector_qualified_animal_visit_count == 1
        # ...it must appear as confirmed, exactly once...
        confirmed = [
            species.label for species in after.new_today
        ]
        assert confirmed.count("northern_cardinal") == 1
        # ...and it must no longer be double-counted as merely likely.
        assert all(
            species.label != "northern_cardinal" for species in after.likely_today
        )
    finally:
        repository.close()


def test_best_moments_still_surface_a_confirmed_visit(tmp_path) -> None:
    """"Best moments" is evidence-backed, so it depended on the same lookup."""

    repository = _repository(tmp_path)
    try:
        _add_visit(
            repository,
            visit_id="moment",
            observed_at=_NOW,
            reviewed_label="northern_cardinal",
        )

        today = repository.dashboard_summary(
            now=_NOW, local_date=_NOW.date()
        ).today

        assert today.detector_qualified_animal_visit_count == 1
        assert [moment.id for moment in today.best_moments] == ["moment"]
    finally:
        repository.close()


def test_dashboard_reads_write_nothing(tmp_path) -> None:
    """A read-only build stays read-only, and Reviewed truth is untouched."""

    repository = _repository(tmp_path)
    try:
        _add_visit(
            repository,
            visit_id="visitor",
            observed_at=_NOW,
            reviewed_label="northern_cardinal",
        )

        def _counts() -> tuple[int, ...]:
            with repository.session_factory() as session:
                return (
                    session.scalar(select(func.count(EventModel.id))) or 0,
                    session.scalar(select(func.count(VisitModel.id))) or 0,
                    session.scalar(select(func.count(ReviewLabelModel.id))) or 0,
                    session.scalar(select(func.count(MotionEvidenceModel.id))) or 0,
                    session.scalar(select(func.count(MediaAssetModel.id))) or 0,
                )

        before = _counts()
        repository.dashboard_summary(now=_NOW, local_date=_NOW.date())
        repository.review_queue_items()
        assert _counts() == before

        with repository.session_factory() as session:
            visit = session.get(VisitModel, "visitor")
            assert visit is not None
            assert visit.reviewed_label == "northern_cardinal"
            assert visit.review_status == "reviewed"
    finally:
        repository.close()


def _classify_motion_evidence_reads(repository: ProductRepository, call):
    """Split MotionEvidence reads into bulk preloads and per-target misses.

    Today's per-Visit cost is genuinely large for reasons this milestone
    does not touch (and `_motion_evidence_model_for_visit` is a separate,
    older, oldest-first lookup this repair never sees), so a total
    statement count would isolate nothing. These two shapes are exact:
    `_motion_evidence_for_review_queue_item`'s fall-through query is the
    only `motion_evidence` read ordered `created_at DESC`, and the
    preloads are the only ones using `IN`.
    """

    counts = {"fall_through": 0, "bulk": 0}

    def _on_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        normalized = " ".join(statement.split()).lower()
        if not normalized.startswith("select motion_evidence."):
            return
        if "motion_evidence.created_at desc" in normalized:
            counts["fall_through"] += 1
        elif " in (" in normalized:
            counts["bulk"] += 1

    sa_event.listen(repository.engine, "before_cursor_execute", _on_execute)
    try:
        result = call()
    finally:
        sa_event.remove(repository.engine, "before_cursor_execute", _on_execute)
    return counts, result


def test_today_motion_evidence_reads_do_not_scale_with_the_day(tmp_path) -> None:
    """Correctness here must not cost one round trip per Visit.

    The repaired lookup refuses to answer for targets outside the queue's
    preload, and Today's Visits are exactly that. Rather than fall through
    per Visit, Today declares its own bounded day set to the same preload
    -- so a busy day costs the same number of MotionEvidence reads as a
    quiet one. A structural assertion: statement shape, not wall clock.
    """

    small = _repository(tmp_path, "small.sqlite3")
    large = _repository(tmp_path, "large.sqlite3")
    try:
        for repository, confirmed in ((small, 5), (large, 50)):
            for index in range(confirmed):
                _add_visit(
                    repository,
                    visit_id=f"confirmed-{index:03d}",
                    reviewed_label="northern_cardinal",
                )
            _add_visit(repository, visit_id="pending")

        small_reads, small_summary = _classify_motion_evidence_reads(
            small, lambda: small.dashboard_summary(now=_NOW, local_date=_NOW.date())
        )
        large_reads, large_summary = _classify_motion_evidence_reads(
            large, lambda: large.dashboard_summary(now=_NOW, local_date=_NOW.date())
        )

        # Both days are counted correctly -- the regression made both 1.
        assert small_summary.today.detector_qualified_animal_visit_count == 6
        assert large_summary.today.detector_qualified_animal_visit_count == 51

        # Ten times the day's Visits, the same handful of bulk reads and
        # not one per-target miss. Falling through would be two per Visit.
        assert small_reads["fall_through"] == 0
        assert large_reads["fall_through"] == 0
        assert large_reads["bulk"] == small_reads["bulk"]
    finally:
        small.close()
        large.close()
