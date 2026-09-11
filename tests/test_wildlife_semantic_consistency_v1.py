"""Wildlife Semantic Consistency v1 -- cross-surface regression coverage for
the exact defect this milestone closes (see docs/wildlife-semantic-
consistency-v1-contract.md): a Visit whose human review confirms wildlife
presence but honestly abstains on species (an "unknown_bird"/"unknown_
animal"/"ambiguous" correction) must read as confirmed wildlife activity --
consistently -- on Today, Bird Log, and Local Data. Before this fix, the
identical fact was "confirmed" on Today and "not confirmed" on Bird Log and
Local Data, one click apart (docs/release-experience-rehearsal-v1-report.md
Section 3.5).

Fixture conventions mirror tests/test_everyday_discovery_ux_closure.py
(isolated file-backed repository + real ASGI HTTP client +
`review_origin="human"` correction helper) rather than inventing a second
pattern for the same kind of product-loop test. One canonical scenario
(`build_scenario`) is reused by every cross-surface test in this file, per
this milestone's own "prefer one canonical fixture" instruction.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.storage.models import (
    CameraSourceModel,
    EventModel,
    MediaAssetModel,
    StreamModel,
    VisitEvidenceLinkModel,
    VisitModel,
    ZoneModel,
)
from tests.conftest import LegacyAuthenticatedTestClient

SOURCE_ID = "source-wildlife-semantic"
STREAM_ID = "stream-wildlife-semantic"
ZONE_ID = "zone-wildlife-semantic"

# Fixed instant, self-consistent everywhere it is used (query windows are
# always relative to this, never the real wall clock) -- matches this
# codebase's own established convention for a deterministic fixture time.
NOW = datetime(2026, 9, 11, 12, 0, tzinfo=UTC)

pytestmark = pytest.mark.anyio


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path) -> ProductRepository:
    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
    )
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client():
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


def add_graph(repository: ProductRepository) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                CameraSourceModel(
                    id=SOURCE_ID,
                    name="Wildlife Semantic Consistency fixture camera",
                    kind="manual_upload",
                    status="connected",
                    description="Wildlife Semantic Consistency v1 fixture source.",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID,
                    source_id=SOURCE_ID,
                    name="Wildlife Semantic Consistency fixture stream",
                    description="Wildlife Semantic Consistency v1 fixture stream.",
                    is_live=False,
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
                    monitoring_policy_json=None,
                )
            )


def add_visit_with_media(
    repository: ProductRepository,
    *,
    visit_id: str,
    started_at: datetime,
    species_guess: str | None,
) -> None:
    """One Visit with a real (tiny) image MediaAsset linked via
    VisitEvidenceLinkModel, needs_review until reviewed by the `review()`
    helper -- the evidence shape Local Data's storage summary and Bird
    Log/Today's Visit resolvers all read."""

    event_id = f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                EventModel(
                    id=event_id,
                    stream_id=STREAM_ID,
                    title=f"Wildlife Semantic Consistency fixture {visit_id}",
                    event_type="observation_engine_candidate",
                    started_at=started_at,
                    ended_at=started_at + timedelta(seconds=7),
                    primary_zone_id=ZONE_ID,
                    review_status="needs_review",
                )
            )
            media_path = repository.media_root / f"{visit_id}.jpg"
            media_path.parent.mkdir(parents=True, exist_ok=True)
            fixture_bytes = b"fixture-jpeg-bytes"
            media_path.write_bytes(fixture_bytes)
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=event_id,
                    subject_label="bird",
                    species_guess=species_guess,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=None,
                    zone_id=ZONE_ID,
                    is_superseded=False,
                )
            )
            media_id = f"media-{visit_id}"
            session.add(
                MediaAssetModel(
                    id=media_id,
                    source_id=SOURCE_ID,
                    stream_id=STREAM_ID,
                    filename=f"{media_id}.jpg",
                    content_type="image/jpeg",
                    media_type="image",
                    local_path=str(media_path),
                    original_filename=f"{media_id}.jpg",
                    file_size_bytes=len(fixture_bytes),
                    created_at=started_at,
                    image_width=640,
                    image_height=480,
                )
            )
            session.add(
                VisitEvidenceLinkModel(
                    id=f"link-{visit_id}",
                    visit_id=visit_id,
                    media_asset_id=media_id,
                    captured_at=started_at,
                    frame_sequence=0,
                    sort_order=0,
                    is_primary=True,
                    created_at=started_at,
                )
            )


async def review(client: httpx.AsyncClient, visit_id: str, label: str) -> None:
    response = await client.post(
        "/api/review-labels",
        json={"review_origin": "human", "target_type": "visit", "target_id": visit_id, "label": label},
    )
    assert response.status_code == 201, response.text


async def build_scenario(client: httpx.AsyncClient, repository: ProductRepository) -> None:
    """Four Visits covering every case the locked semantic contract
    distinguishes (docs/wildlife-semantic-consistency-v1-contract.md):

    - "visit-unknown": B -- reviewed wildlife presence + unknown species.
      The exact defect this milestone closes.
    - "visit-cardinal": A -- reviewed wildlife presence + reviewed species.
      Must be unaffected by this milestone's fix.
    - "visit-false-positive": E -- rejected/non-wildlife evidence. Must
      never read as confirmed wildlife on any surface.
    - "visit-pending": inferred/unreviewed activity. Must never silently
      become Reviewed.
    """

    add_graph(repository)

    add_visit_with_media(
        repository, visit_id="visit-unknown", started_at=NOW - timedelta(minutes=30), species_guess=None
    )
    await review(client, "visit-unknown", "unknown_bird")

    add_visit_with_media(
        repository,
        visit_id="visit-cardinal",
        started_at=NOW - timedelta(minutes=20),
        species_guess="northern_cardinal",
    )
    await review(client, "visit-cardinal", "northern_cardinal")

    add_visit_with_media(
        repository, visit_id="visit-false-positive", started_at=NOW - timedelta(minutes=10), species_guess=None
    )
    await review(client, "visit-false-positive", "false_positive")

    add_visit_with_media(
        repository, visit_id="visit-pending", started_at=NOW - timedelta(minutes=5), species_guess="blue_jay"
    )


async def test_today_report_confirms_wildlife_with_unresolved_species(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    """Regression guard, not the fix itself: `place_activity_report.py`
    already had this right (docs/place-activity-report-contract.md's
    "Wildlife classification boundary") before this milestone -- proves
    nothing this milestone touched broke it."""

    await build_scenario(client, isolated_repository)

    response = await client.post(
        "/api/analytics/place-activity-report",
        json={
            "start_at": (NOW - timedelta(hours=1)).isoformat(),
            "end_at": (NOW + timedelta(hours=1)).isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()

    # "visit-unknown" + "visit-cardinal" are both confirmed wildlife;
    # "visit-false-positive" is rejected/non-wildlife; "visit-pending" is
    # not yet reviewed -- neither of the latter two counts.
    assert body["confirmed_wildlife_visit_count"] == 2
    assert body["confirmed_species_unresolved_visit_count"] == 1

    taxa_labels = {taxon["label"] for taxon in body["taxa"]}
    assert "northern_cardinal" in taxa_labels
    # Never fabricated into a named taxon entry.
    assert "unknown_bird" not in taxa_labels
    assert "false_positive" not in taxa_labels


async def test_bird_log_agrees_with_today_on_the_same_visit(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    await build_scenario(client, isolated_repository)

    response = await client.get("/api/bird-log/journal", params={"stream_id": STREAM_ID})
    assert response.status_code == 200, response.text
    body = response.json()
    labels = {item["label"] for item in body["labels"]}

    # The exact cross-surface consistency this milestone requires: the
    # identical fact Today counts as `confirmed_species_unresolved_visit_
    # count == 1` above must read the same way here -- not "no confirmed
    # wildlife observations," the reproduced defect.
    assert body["confirmed_species_unresolved_visit_count"] == 1
    assert "northern_cardinal" in labels
    # Honest abstention: never fabricated into a fake per-species label
    # (unchanged from before this milestone -- see
    # test_bird_log_reflects_all_confirmed_scenarios_honestly).
    assert "unknown_bird" not in labels
    assert "false_positive" not in labels


async def test_bird_log_never_claims_nothing_confirmed_when_only_unidentified_wildlife_exists(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    """The precise reported symptom (docs/release-experience-rehearsal-v1-
    report.md Section 3.5): a Bird Log with *zero* named-species labels but
    one real reviewed "Unknown Bird" Visit must not be indistinguishable
    from a Bird Log with genuinely nothing confirmed at all."""

    add_graph(isolated_repository)
    add_visit_with_media(
        isolated_repository, visit_id="visit-unknown-only", started_at=NOW, species_guess=None
    )
    await review(client, "visit-unknown-only", "unknown_bird")

    response = await client.get("/api/bird-log/journal", params={"stream_id": STREAM_ID})
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["labels"] == []
    assert body["confirmed_species_unresolved_visit_count"] == 1


async def test_local_data_counts_unresolved_wildlife_as_reviewed_wildlife(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    await build_scenario(client, isolated_repository)

    response = await client.get("/api/settings/storage-retention/summary")
    assert response.status_code == 200, response.text
    body = response.json()

    # "visit-unknown" (unresolved wildlife) + "visit-cardinal" (named
    # species) both count as reviewed wildlife -- the pre-fix defect
    # undercounted "visit-unknown" as "reviewed other" instead (see
    # tests/test_storage_retention.py's updated `_storage_visit_is_
    # wildlife` coverage for the underlying unit-level proof). The demo
    # first-run seed content creates no real MediaAsset rows, so it cannot
    # pollute this count either way.
    assert body["reviewed_bird_wildlife_evidence_count"] == 2
    assert body["reviewed_non_bird_blank_ambiguous_evidence_count"] == 1
    assert body["unresolved_visit_evidence_count"] == 1


async def test_rejected_review_never_appears_as_confirmed_wildlife_anywhere(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    """Abstention (unknown_bird) and outright rejection (false_positive)
    must never be conflated on any of the three surfaces -- both are
    "reviewed," only one is confirmed wildlife."""

    await build_scenario(client, isolated_repository)

    bird_log = await client.get("/api/bird-log/journal", params={"stream_id": STREAM_ID})
    assert "false_positive" not in {item["label"] for item in bird_log.json()["labels"]}

    today = await client.post(
        "/api/analytics/place-activity-report",
        json={
            "start_at": (NOW - timedelta(hours=1)).isoformat(),
            "end_at": (NOW + timedelta(hours=1)).isoformat(),
        },
    )
    assert "false_positive" not in {taxon["label"] for taxon in today.json()["taxa"]}

    storage = await client.get("/api/settings/storage-retention/summary")
    # The rejected Visit is the one contributor to "reviewed other" in this
    # scenario (see test_local_data_counts_unresolved_wildlife_as_reviewed_
    # wildlife above) -- confirming it, not the abstained one, landed there.
    assert storage.json()["reviewed_non_bird_blank_ambiguous_evidence_count"] == 1
