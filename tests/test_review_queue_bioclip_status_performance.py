"""BioCLIP Status / Review Queue Performance v1.

Focused, deterministic call-count/interaction tests proving
`get_bioclip_status()` (and the model-adapter registry it feeds) is
resolved once per bounded repository operation -- not once per review
item -- while every other observable behavior (adapter selection, status
values, candidate-pack resolution, review correction truth) stays exactly
as before. See docs/bioclip-review-queue-performance-contract.md.

These tests use a call-counting stand-in for `get_bioclip_status()` rather
than real local model artifacts (the existing `mark_bioclip_available`
pattern in tests/test_review_identification.py). Real per-call cost and
wall-clock acceptance are covered separately by real Windows/GPU packaged
acceptance -- these tests prove call-count/interaction structure, which is
deterministic and environment-independent, not wall-clock timing.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from mockingbird.api.schemas import (
    ReviewIdentificationStatus,
    ReviewQueueBulkCorrectionRequest,
    ReviewQueueBulkCorrectionTargetType,
    ReviewQueueSpeciesSuggestionBatchPrepareRequest,
    SpeciesCandidatePackCreate,
    StreamSpeciesCandidatePackSelectionUpdate,
)
from mockingbird.repository import product_repository
from mockingbird.repository.product_repository import (
    DetectionProposalModel,
    DetectionRunModel,
    MotionEvidenceModel,
    ProductRepository,
    SpeciesSuggestionModel,
)
from mockingbird.species.bioclip_adapter import BIOCLIP_ADAPTER_ID
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    StreamModel,
    VisitModel,
    ZoneModel,
)

SOURCE_ID = "source-bioclip-perf"
STREAM_ID = "stream-bioclip-perf"
ZONE_ID = "zone-bioclip-perf"
BASE_TIME = datetime(2026, 8, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    with repo.session_factory() as session:
        with session.begin():
            # Archiving the demo Source (as tests/test_dashboard_today.py's
            # fixture also does) does not remove its own still-
            # needs-review seeded demo Visit/Event from
            # `_review_queue_items()`, which is not day- or Source-scoped
            # the way Today's own summary is. Resolve that one seeded
            # item explicitly so these exact item-count assertions are
            # attributable to this fixture's own data only.
            demo = session.get(CameraSourceModel, "source-backyard-demo")
            if demo is not None:
                demo.status = "archived"
            demo_event = session.get(EventModel, "event-bird-feeder-001")
            if demo_event is not None:
                demo_event.review_status = "reviewed"
            demo_visit = session.get(VisitModel, "visit-bird-feeder-001")
            if demo_visit is not None:
                demo_visit.review_status = "reviewed"
                demo_visit.reviewed_label = "northern_cardinal"
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID,
                    name="Perf camera",
                    kind="integration",
                    status="connected",
                    description="BioCLIP review-queue performance fixture.",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID,
                    source_id=SOURCE_ID,
                    name="Perf stream",
                    description="BioCLIP review-queue performance fixture.",
                    is_live=True,
                )
            )
            session.add(
                ZoneModel(
                    id=ZONE_ID,
                    stream_id=STREAM_ID,
                    name="Feeder",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                )
            )
    return repo


def add_review_visit(
    repository: ProductRepository,
    *,
    visit_id: str,
    index: int,
    stream_id: str = STREAM_ID,
    source_id: str = SOURCE_ID,
    zone_id: str | None = ZONE_ID,
    subject_label: str = "unknown_bird",
    with_species_suggestion: bool = False,
    with_detection_proposal: bool = False,
) -> None:
    """Seed one unresolved, media-backed, evidence-backed Visit -- the
    minimal shape `_review_queue_items` needs to build a full
    `ReviewIdentificationSummary` (matching the real backlog shape that
    exposed the defect, not a degenerate media-less fixture)."""

    event_id = f"event-{visit_id}"
    media_id = f"media-{visit_id}"
    observed_at = BASE_TIME - timedelta(minutes=index)
    media_path = repository.media_root / f"{visit_id}.jpg"
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_bytes(b"\xff\xd8\xff\xd9")

    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_id,
                    source_id=source_id,
                    stream_id=stream_id,
                    filename=f"{visit_id}.jpg",
                    content_type="image/jpeg",
                    media_type="image",
                    local_path=str(media_path),
                    original_filename=f"{visit_id}.jpg",
                    file_size_bytes=media_path.stat().st_size,
                    created_at=observed_at,
                    captured_at=observed_at,
                    notes="Perf fixture.",
                )
            )
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=stream_id,
                    title=f"Perf visit {visit_id}",
                    event_type="durable_monitoring_visit",
                    started_at=observed_at,
                    ended_at=observed_at + timedelta(seconds=20),
                    primary_zone_id=zone_id,
                    review_status="needs_review",
                )
            )
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label=subject_label,
                    species_guess=None,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=str(media_path),
                    zone_id=zone_id,
                    is_superseded=False,
                )
            )
            session.add(
                MotionEvidenceModel(
                    id=f"evidence-{visit_id}",
                    source_id=source_id,
                    stream_id=stream_id,
                    zone_id=zone_id,
                    start_frame_index=None,
                    end_frame_index=None,
                    best_frame_index=None,
                    start_time=None,
                    end_time=None,
                    best_frame_time=None,
                    peak_changed_ratio=0.1,
                    triggered_frame_count=1,
                    scoring_config_json=json.dumps({}),
                    snapshot_media_asset_id=media_id,
                    status="promoted",
                    promoted_event_id=event_id,
                    promoted_visit_id=visit_id,
                    created_at=observed_at,
                    notes=None,
                )
            )
            if with_species_suggestion:
                session.add(
                    SpeciesSuggestionModel(
                        id=f"suggestion-{visit_id}",
                        source_id=source_id,
                        stream_id=stream_id,
                        event_id=event_id,
                        visit_id=visit_id,
                        media_asset_id=media_id,
                        adapter_id=BIOCLIP_ADAPTER_ID,
                        adapter_name="BioCLIP 2",
                        suggested_label="northern_cardinal",
                        suggested_common_name="Northern Cardinal",
                        suggested_scientific_name="Cardinalis cardinalis",
                        confidence=0.42,
                        rank=1,
                        alternatives_json="[]",
                        evidence_region_json=None,
                        status="pending",
                        created_at=observed_at,
                        notes=None,
                    )
                )
            if with_detection_proposal:
                run_id = f"run-{visit_id}"
                session.add(
                    DetectionRunModel(
                        id=run_id,
                        media_asset_id=media_id,
                        source="megadetector",
                        summary="megadetector",
                        status="completed",
                        created_at=observed_at,
                        completed_at=observed_at,
                    )
                )
                session.add(
                    DetectionProposalModel(
                        id=f"proposal-{visit_id}",
                        run_id=run_id,
                        media_asset_id=media_id,
                        stream_id=stream_id,
                        zone_id=zone_id,
                        event_id=event_id,
                        visit_id=visit_id,
                        label="animal",
                        confidence=0.8,
                        bbox_json=None,
                        suggested_event_type="animal_visit",
                        suggested_subject_label="unknown_animal",
                        suggested_species=None,
                        status="proposed",
                        notes=None,
                        created_at=observed_at,
                    )
                )


def _bioclip_status_namespace(
    *,
    status: str,
    model_dir: Path,
    labels_path: Path,
    embedding_cache_path: Path,
) -> SimpleNamespace:
    return SimpleNamespace(
        status=status,
        configured=True,
        runtime_available=(status == "available"),
        detail=f"Mock BioCLIP status for performance test (status={status}).",
        model_dir=str(model_dir),
        labels_path=str(labels_path),
        embedding_cache_path=str(embedding_cache_path),
        device="cpu",
        labels_sha256="a" * 64,
    )


def install_counting_bioclip_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    status: str = "available",
) -> dict[str, int]:
    """Monkeypatch `product_repository.get_bioclip_status` with a call-
    counting stub -- the same seam tests/test_review_identification.py's
    `mark_bioclip_available` patches, extended with a call counter for
    deterministic interaction assertions instead of real local artifacts."""

    model_dir = tmp_path / "bioclip-model"
    labels_path = tmp_path / "bioclip-labels.txt"
    cache_path = tmp_path / "bioclip-embeddings.npz"
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_MODEL_PATH", str(model_dir))
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_LABELS_PATH", str(labels_path))
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH", str(cache_path))

    counters = {"n": 0}

    def counting_status(config):
        counters["n"] += 1
        return _bioclip_status_namespace(
            status=status,
            model_dir=model_dir,
            labels_path=labels_path,
            embedding_cache_path=cache_path,
        )

    monkeypatch.setattr(product_repository, "get_bioclip_status", counting_status)
    return counters


def install_landmine_bioclip_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    safe_call_budget: int = 2,
) -> dict[str, int]:
    """Returns "available" for the first `safe_call_budget` calls, then
    "unavailable" for every call after. A per-operation resolution stays
    inside the budget and never detonates the landmine; the old always-
    resolve-per-item behavior blows through it well before the backlog
    ends, producing a visible mid-operation status split that the
    per-operation fix must never reproduce."""

    model_dir = tmp_path / "bioclip-model"
    labels_path = tmp_path / "bioclip-labels.txt"
    cache_path = tmp_path / "bioclip-embeddings.npz"
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_MODEL_PATH", str(model_dir))
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_LABELS_PATH", str(labels_path))
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH", str(cache_path))

    counters = {"n": 0}

    def landmine_status(config):
        counters["n"] += 1
        status = "available" if counters["n"] <= safe_call_budget else "unavailable"
        return _bioclip_status_namespace(
            status=status,
            model_dir=model_dir,
            labels_path=labels_path,
            embedding_cache_path=cache_path,
        )

    monkeypatch.setattr(product_repository, "get_bioclip_status", landmine_status)
    return counters


def _bioclip_items(items) -> list:
    return [
        item
        for item in items
        if item.identification is not None and item.identification.adapter_id == BIOCLIP_ADAPTER_ID
    ]


@pytest.mark.parametrize("item_count", [3, 12])
def test_review_queue_items_bioclip_calls_stay_bounded_as_backlog_grows(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    item_count: int,
) -> None:
    """Core regression: this would fail under the pre-fix O(N) behavior,
    where call count scaled at ~2-4x item_count (confirmed by hermetic
    profiling: 19/69/152/292 calls for 5/20/45/87 items)."""

    counters = install_counting_bioclip_status(monkeypatch, tmp_path)
    for index in range(item_count):
        add_review_visit(
            repository,
            visit_id=f"visit-{index:03d}",
            index=index,
            with_species_suggestion=(index % 3 == 0),
            with_detection_proposal=(index % 2 == 0),
        )

    items = repository.review_queue_items()

    assert len(items) == item_count
    assert len(_bioclip_items(items)) == item_count
    # One generic model-adapter-registry resolution plus at most one
    # stream/pack-scoped resolution for this single-stream backlog --
    # never proportional to `item_count`.
    assert counters["n"] <= 2, (
        f"get_bioclip_status() ran {counters['n']} times for {item_count} "
        "review items; expected a small constant, not backlog-proportional growth"
    )


def test_dashboard_summary_resolves_bioclip_status_once_per_request(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    counters = install_counting_bioclip_status(monkeypatch, tmp_path)
    for index in range(15):
        add_review_visit(
            repository,
            visit_id=f"dash-{index:03d}",
            index=index,
            with_species_suggestion=True,
        )

    summary = repository.dashboard_summary()

    assert summary.headline.needs_review_visit_count == 15
    assert counters["n"] <= 2


def test_species_suggestion_batch_preflight_shares_one_status_resolution(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`prepare_review_queue_species_suggestions` is a second, independent
    O(N) call site (a review/correction-adjacent bulk path, not
    `_review_queue_items`) that the same defect and fix cover."""

    counters = install_counting_bioclip_status(monkeypatch, tmp_path)
    visit_ids = []
    for index in range(20):
        visit_id = f"batch-{index:03d}"
        add_review_visit(repository, visit_id=visit_id, index=index)
        visit_ids.append(visit_id)

    response = repository.prepare_review_queue_species_suggestions(
        ReviewQueueSpeciesSuggestionBatchPrepareRequest(visit_ids=visit_ids)
    )

    assert response.requested_count == 20
    assert response.queued_count == 20
    assert counters["n"] <= 2


def test_one_operation_observes_one_coherent_status_within_budget(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Proves "a single logical request observes one coherent adapter-
    availability state": every item in the same `review_queue_items()`
    call must agree, even against a status source primed to disagree with
    itself once call count crosses a small budget."""

    counters = install_landmine_bioclip_status(monkeypatch, tmp_path, safe_call_budget=2)
    for index in range(10):
        add_review_visit(
            repository,
            visit_id=f"coherent-{index:03d}",
            index=index,
            with_species_suggestion=True,
        )

    items = repository.review_queue_items()
    bioclip_items = _bioclip_items(items)

    assert len(bioclip_items) == 10
    statuses = {item.identification.status for item in bioclip_items}
    can_run_values = {item.identification.can_run for item in bioclip_items}
    assert len(statuses) == 1, f"expected one coherent status, got {statuses}"
    assert len(can_run_values) == 1, f"expected one coherent can_run, got {can_run_values}"
    assert counters["n"] <= 2


def test_status_change_is_visible_at_the_next_operation_boundary(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Negative control: per-operation resolution must never become a
    process-level cache. A genuine environment change (e.g. the local
    model directory disappearing) between two separate operations must be
    visible at the next operation, not hidden behind a stale result."""

    model_dir = tmp_path / "bioclip-model"
    labels_path = tmp_path / "bioclip-labels.txt"
    cache_path = tmp_path / "bioclip-embeddings.npz"
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_MODEL_PATH", str(model_dir))
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_LABELS_PATH", str(labels_path))
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH", str(cache_path))
    state = {"status": "available"}

    def controllable_status(config):
        return _bioclip_status_namespace(
            status=state["status"],
            model_dir=model_dir,
            labels_path=labels_path,
            embedding_cache_path=cache_path,
        )

    monkeypatch.setattr(product_repository, "get_bioclip_status", controllable_status)
    # No pre-existing suggestion/proposal on purpose: `status` reports
    # `suggestion_present`/`proposal_present` ahead of availability once
    # evidence already exists (an intentional, unrelated, pre-existing
    # precedence rule -- see `_review_identification_summary_for_item`),
    # so a bare Visit is what isolates the availability-driven status
    # this test is about.
    add_review_visit(repository, visit_id="boundary-visit", index=0)

    first_items = _bioclip_items(repository.review_queue_items())
    assert len(first_items) == 1
    assert first_items[0].identification.can_run is True
    assert first_items[0].identification.status == ReviewIdentificationStatus.configured_available

    # Simulate the local model artifact disappearing between requests.
    state["status"] = "unavailable"

    second_items = _bioclip_items(repository.review_queue_items())
    assert len(second_items) == 1
    assert second_items[0].identification.can_run is False
    assert second_items[0].identification.status != ReviewIdentificationStatus.configured_available


def test_unavailable_bioclip_adapter_reports_consistently_and_cheaply(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unavailable-adapter behavior (BioCLIP never configured at all) must
    keep working exactly as before, and must not itself become expensive."""

    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_LABELS_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH", raising=False)
    real_status = product_repository.get_bioclip_status
    counters = {"n": 0}

    def counting(config):
        counters["n"] += 1
        return real_status(config)

    monkeypatch.setattr(product_repository, "get_bioclip_status", counting)

    for index in range(8):
        # No pre-existing suggestion: see the comment in
        # test_status_change_is_visible_at_the_next_operation_boundary --
        # `suggestion_present` would otherwise take status precedence over
        # the availability-driven statuses this test checks.
        add_review_visit(
            repository,
            visit_id=f"unavail-{index:03d}",
            index=index,
        )

    items = repository.review_queue_items()
    bioclip_items = _bioclip_items(items)

    assert len(bioclip_items) == 8
    assert all(item.identification.can_run is False for item in bioclip_items)
    assert all(
        item.identification.status
        in {ReviewIdentificationStatus.setup_required, ReviewIdentificationStatus.unavailable}
        for item in bioclip_items
    )
    assert counters["n"] <= 2


def test_multi_stream_candidate_packs_resolve_independently_within_one_operation(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The pack-scoped half of the fix must not conflate different
    Streams' candidate packs into one cached answer -- it must key on the
    exact candidate-label tuple, not collapse to a single operation-wide
    value the way the adapter-registry status correctly does."""

    counters = install_counting_bioclip_status(monkeypatch, tmp_path)
    second_source_id, second_stream_id, second_zone_id = (
        "source-bioclip-perf-2",
        "stream-bioclip-perf-2",
        "zone-bioclip-perf-2",
    )
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=second_source_id,
                    name="Second perf camera",
                    kind="integration",
                    status="connected",
                    description="fixture",
                )
            )
            session.add(
                StreamModel(
                    id=second_stream_id,
                    source_id=second_source_id,
                    name="Second perf stream",
                    description="fixture",
                    is_live=True,
                )
            )
            session.add(
                ZoneModel(
                    id=second_zone_id,
                    stream_id=second_stream_id,
                    name="Feeder 2",
                    zone_type="feeder",
                    polygon_json="[]",
                    is_active=True,
                )
            )

    pack = repository.create_species_candidate_pack(
        SpeciesCandidatePackCreate(
            display_name="Narrow perf pack",
            taxonomy_label_ids=["tufted_titmouse", "carolina_chickadee"],
        )
    )
    repository.set_stream_species_candidate_pack_selection(
        second_stream_id,
        StreamSpeciesCandidatePackSelectionUpdate(candidate_pack_id=pack.id),
    )

    for index in range(4):
        add_review_visit(
            repository,
            visit_id=f"first-{index}",
            index=index,
            with_species_suggestion=True,
        )
    for index in range(4):
        add_review_visit(
            repository,
            visit_id=f"second-{index}",
            index=index,
            stream_id=second_stream_id,
            source_id=second_source_id,
            zone_id=second_zone_id,
            with_species_suggestion=True,
        )

    items = repository.review_queue_items()
    first_items = _bioclip_items([item for item in items if item.stream_id == STREAM_ID])
    second_items = _bioclip_items([item for item in items if item.stream_id == second_stream_id])

    assert len(first_items) == 4
    assert len(second_items) == 4
    assert all(item.identification.candidate_pack.id == "backyard-core" for item in first_items)
    assert all(item.identification.candidate_pack.id == pack.id for item in second_items)
    # 1 generic resolution + 2 distinct pack-scoped resolutions (one per
    # distinct Stream/pack) -- never proportional to the 8 total items.
    assert counters["n"] <= 3


def test_bulk_correction_after_shared_status_resolution_creates_correct_truth(
    repository: ProductRepository,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Review mutations must preserve correctness: sharing adapter-status
    resolution across a batch read must not leak into, or be disturbed
    by, a truth-writing correction."""

    install_counting_bioclip_status(monkeypatch, tmp_path)
    visit_ids = []
    for index in range(5):
        visit_id = f"mut-{index}"
        add_review_visit(repository, visit_id=visit_id, index=index, with_species_suggestion=True)
        visit_ids.append(visit_id)

    # Reading the queue once first (as the UI would) must not affect the
    # correction outcome below.
    repository.review_queue_items()

    response = repository.bulk_correct_review_queue_items(
        ReviewQueueBulkCorrectionRequest(
            target_ids=visit_ids,
            target_type=ReviewQueueBulkCorrectionTargetType.visit,
            label="northern_cardinal",
            review_origin="human",
        )
    )

    assert response.requested_count == 5
    assert response.succeeded_count == 5
    assert response.failed_count == 0
    assert response.skipped_count == 0

    with repository.session_factory() as session:
        for visit_id in visit_ids:
            visit = session.get(VisitModel, visit_id)
            assert visit is not None
            assert visit.review_status == "reviewed"
            assert visit.reviewed_label == "northern_cardinal"

    # The now-reviewed Visits must have left the unresolved queue.
    remaining = repository.review_queue_items()
    assert not any(item.target_id in visit_ids for item in remaining)
