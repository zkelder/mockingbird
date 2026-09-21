"""Everyday Product / Discovery UX Closure v1 -- focused regressions for the
concrete defects fixed in this milestone (Today/Evidence/Review/Bird Log).

Fixture conventions mirror tests/test_wildlife_journal.py (isolated
file-backed repository + real ASGI HTTP client + `review_origin="human"`
correction helper) rather than inventing a second pattern for the same kind
of product-loop test.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository.product_repository import (
    AcousticDetectionFacts,
    ProductRepository,
    SpeciesSuggestionModel,
)
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

SOURCE_ID = "source-everyday-ux"
STREAM_ID = "stream-everyday-ux"
ZONE_ID = "zone-everyday-ux"

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
                    name="Everyday UX fixture camera",
                    kind="manual_upload",
                    status="connected",
                    description="Everyday Product / Discovery UX Closure v1 fixture source.",
                )
            )
            session.add(
                StreamModel(
                    id=STREAM_ID,
                    source_id=SOURCE_ID,
                    name="Everyday UX fixture stream",
                    description="Everyday Product / Discovery UX Closure v1 fixture stream.",
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
    event_id: str | None = None,
    started_at: datetime,
    species_guess: str | None,
    set_representative_media_path: bool,
) -> None:
    """One Visit with a real (tiny) image MediaAsset linked via
    VisitEvidenceLinkModel -- the Stage 7 / Observation Engine evidence
    shape (evidence_frames-backed), optionally also setting the legacy
    representative_media_path field so both code paths can be exercised."""

    resolved_event_id = event_id or f"event-{visit_id}"
    with repository.session_factory() as session:
        with session.begin():
            if session.get(EventModel, resolved_event_id) is None:
                session.add(
                    EventModel(
                        id=resolved_event_id,
                        stream_id=STREAM_ID,
                        title=f"Everyday UX fixture {visit_id}",
                        # Matches the dominant current architecture (Camera
                        # Node/offline ingest, `_create_candidate_visit_
                        # locked`) -- also what Today's own detector-
                        # qualification gate (`_review_queue_product_context`)
                        # requires to count this as an "animal" visit at all.
                        event_type="observation_engine_candidate",
                        started_at=started_at,
                        ended_at=started_at + timedelta(seconds=7),
                        primary_zone_id=ZONE_ID,
                        review_status="needs_review",
                    )
                )
            media_path = repository.media_root / f"{visit_id}.jpg"
            media_path.parent.mkdir(parents=True, exist_ok=True)
            media_path.write_bytes(b"fixture-jpeg-bytes")
            session.add(
                VisitModel(
                    id=visit_id,
                    event_id=resolved_event_id,
                    subject_label="bird",
                    species_guess=species_guess,
                    confidence=None,
                    reviewed_label=None,
                    review_status="needs_review",
                    representative_media_path=(str(media_path) if set_representative_media_path else None),
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
                    file_size_bytes=12,
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


async def create_acoustic_visit(
    repository: ProductRepository,
    *,
    visit_id_hint: str,
    common_name: str,
    window_start_ms: int = 4_000,
    window_end_ms: int = 10_000,
    observed_at: datetime | None = None,
) -> tuple[str, str]:
    """A real acoustic candidate Visit via the same repository method the
    real BirdNET ingest pipeline calls -- not a hand-built substitute."""

    observed_at = observed_at or datetime(2026, 8, 1, 9, 0, tzinfo=UTC)
    with repository.session_factory() as session:
        with session.begin():
            media_id = f"media-audio-{visit_id_hint}"
            audio_path = repository.media_root / f"{visit_id_hint}.wav"
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            audio_path.write_bytes(b"fixture-wav-bytes")
            session.add(
                MediaAssetModel(
                    id=media_id,
                    source_id=SOURCE_ID,
                    stream_id=STREAM_ID,
                    filename=f"{visit_id_hint}.wav",
                    content_type="audio/wav",
                    media_type="audio",
                    local_path=str(audio_path),
                    original_filename=f"{visit_id_hint}.wav",
                    file_size_bytes=len(b"fixture-wav-bytes"),
                    created_at=observed_at,
                )
            )
    outcome = repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID,
        media_asset_id=media_id,
        detection=AcousticDetectionFacts(
            common_name=common_name,
            scientific_name=None,
            confidence=0.87,
            window_start_ms=window_start_ms,
            window_end_ms=window_end_ms,
        ),
        model_provenance={"adapter": "fixture-birdnet"},
        observed_at=observed_at,
        adapter_id="birdnet",
        adapter_name="BirdNET",
    )
    assert outcome.outcome == "created"
    assert outcome.visit_id is not None and outcome.event_id is not None
    return outcome.visit_id, outcome.event_id


# ---------------------------------------------------------------------------
# P0 D1 -- audio evidence primary player was dead (preview_url 413'd)
# ---------------------------------------------------------------------------


async def test_audio_evidence_frame_resolves_to_file_not_preview(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    add_graph(isolated_repository)
    visit_id, _event_id = await create_acoustic_visit(
        isolated_repository, visit_id_hint="cardinal-audio", common_name="Northern Cardinal"
    )

    detail = await client.get(f"/api/visits/{visit_id}/detail")
    assert detail.status_code == 200
    frames = detail.json()["evidence_frames"]
    assert len(frames) == 1
    assert frames[0]["content_type"] == "audio/wav"
    # The bounded-preview endpoint 413s any non-image asset (see
    # get_media_preview) -- an audio frame must never point there.
    assert frames[0]["preview_url"].endswith("/file")
    assert "/preview" not in frames[0]["preview_url"]

    # Control: the same endpoint actually serves the audio bytes without a 413.
    file_response = await client.get(frames[0]["preview_url"])
    assert file_response.status_code == 200


async def test_image_evidence_frame_still_resolves_to_preview(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    """Regression guard: the audio fix must not change the working image path."""

    add_graph(isolated_repository)
    add_visit_with_media(
        isolated_repository,
        visit_id="robin-image",
        started_at=datetime(2026, 8, 1, 10, 0, tzinfo=UTC),
        species_guess="american_robin",
        set_representative_media_path=False,
    )

    detail = await client.get("/api/visits/robin-image/detail")
    assert detail.status_code == 200
    frames = detail.json()["evidence_frames"]
    assert len(frames) == 1
    assert frames[0]["content_type"] == "image/jpeg"
    assert frames[0]["preview_url"].endswith("/preview")


# ---------------------------------------------------------------------------
# Duration 0 sec -- acoustic Visits now carry the real BirdNET window length
# ---------------------------------------------------------------------------


async def test_acoustic_visit_reports_real_duration_not_zero(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    add_graph(isolated_repository)
    visit_id, _event_id = await create_acoustic_visit(
        isolated_repository,
        visit_id_hint="titmouse-audio",
        common_name="Tufted Titmouse",
        window_start_ms=1_000,
        window_end_ms=7_500,
    )
    await review(client, visit_id, "tufted_titmouse")

    history = await client.get("/api/bird-log/journal/tufted_titmouse")
    assert history.status_code == 200
    observations = history.json()["gallery"]["observations"]
    assert len(observations) == 1
    # 7500ms - 1000ms = 6.5s; previously this was always exactly 0.
    assert observations[0]["duration_seconds"] == pytest.approx(6.5, abs=0.01)


async def test_acoustic_visit_appears_in_todays_confirmed_bird_count(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    """Discovered via live hands-on verification, not a unit test: a real
    acoustic candidate Visit was silently invisible to every Today/Dashboard
    count -- `_review_queue_product_context`'s Stage 7 `detector_class`
    fallback checked only `event_type == "observation_engine_candidate"`,
    never the acoustic sibling `"acoustic_observation_candidate"`."""

    add_graph(isolated_repository)
    visit_id, _event_id = await create_acoustic_visit(
        isolated_repository,
        visit_id_hint="wren-audio",
        common_name="Carolina Wren",
        observed_at=datetime.now(UTC) - timedelta(minutes=15),
    )
    await review(client, visit_id, "carolina_wren")

    summary = await client.get("/api/dashboard/summary")
    assert summary.status_code == 200
    today = summary.json()["today"]
    assert today["confirmed_bird_visit_count"] == 1
    best_moment_ids = {visit["id"] for visit in today["best_moments"]}
    assert visit_id in best_moment_ids


# ---------------------------------------------------------------------------
# P0 -- Bird Log's "confirmed wildlife" was silently birds-only
# ---------------------------------------------------------------------------


async def test_bird_log_overview_includes_confirmed_non_bird_wildlife(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    add_graph(isolated_repository)
    add_visit_with_media(
        isolated_repository,
        visit_id="squirrel-visit",
        started_at=datetime(2026, 8, 1, 11, 0, tzinfo=UTC),
        species_guess=None,
        set_representative_media_path=False,
    )
    await review(client, "squirrel-visit", "squirrel")

    overview = await client.get("/api/bird-log/journal")
    assert overview.status_code == 200
    labels = {item["label"] for item in overview.json()["labels"]}
    assert "squirrel" in labels


async def test_bird_log_history_drilldown_works_for_non_bird_wildlife(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    """Before the fix this 404'd -- the guard required category=="bird"."""

    add_graph(isolated_repository)
    add_visit_with_media(
        isolated_repository,
        visit_id="squirrel-visit-2",
        started_at=datetime(2026, 8, 1, 12, 0, tzinfo=UTC),
        species_guess=None,
        set_representative_media_path=False,
    )
    await review(client, "squirrel-visit-2", "squirrel")

    history = await client.get("/api/bird-log/journal/squirrel")
    assert history.status_code == 200
    observations = history.json()["gallery"]["observations"]
    assert any(item["visit_id"] == "squirrel-visit-2" for item in observations)


async def test_bird_log_still_excludes_non_wildlife_categories(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    """Regression guard: broadening past `confirmed_bird` must not also
    start admitting pets/person/vehicle/false_positive -- only real
    wildlife categories."""

    add_graph(isolated_repository)
    add_visit_with_media(
        isolated_repository,
        visit_id="cat-visit",
        started_at=datetime(2026, 8, 1, 13, 0, tzinfo=UTC),
        species_guess=None,
        set_representative_media_path=False,
    )
    await review(client, "cat-visit", "cat")

    overview = await client.get("/api/bird-log/journal")
    assert overview.status_code == 200
    labels = {item["label"] for item in overview.json()["labels"]}
    assert "cat" not in labels

    history = await client.get("/api/bird-log/journal/cat")
    assert history.status_code == 404


# ---------------------------------------------------------------------------
# Review Queue "Reviewed" tab -- reviewed_label now reaches the wire
# ---------------------------------------------------------------------------


async def test_review_queue_item_carries_reviewed_label(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    add_graph(isolated_repository)
    add_visit_with_media(
        isolated_repository,
        visit_id="cardinal-reviewed",
        started_at=datetime(2026, 8, 1, 14, 0, tzinfo=UTC),
        species_guess="northern_cardinal",
        set_representative_media_path=False,
    )
    await review(client, "cardinal-reviewed", "northern_cardinal")

    queue = await client.get("/api/review-queue", params={"include_reviewed": "true"})
    assert queue.status_code == 200
    items = [item for item in queue.json() if item["target_id"] == "cardinal-reviewed"]
    assert len(items) == 1
    assert items[0]["review_status"] == "reviewed"
    assert items[0]["reviewed_label"] == "northern_cardinal"


# ---------------------------------------------------------------------------
# Local filesystem path redaction (D2/D3)
# ---------------------------------------------------------------------------


async def test_event_detail_redacts_media_asset_local_path(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    add_graph(isolated_repository)
    add_visit_with_media(
        isolated_repository,
        visit_id="path-leak-visit",
        started_at=datetime(2026, 8, 1, 15, 0, tzinfo=UTC),
        species_guess=None,
        set_representative_media_path=True,
    )

    detail = await client.get("/api/events/event-path-leak-visit/detail")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["media_asset"] is not None
    assert payload["media_asset"]["local_path"] == ""
    assert all(visit["representative_media_path"] is None for visit in payload["visits"])


async def test_visit_detail_redacts_sibling_and_resulting_visit_media_paths(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    """Multi-subject siblings: two Visits sharing one Event."""

    add_graph(isolated_repository)
    shared_event_id = "event-multi-subject"
    add_visit_with_media(
        isolated_repository,
        visit_id="sibling-a",
        event_id=shared_event_id,
        started_at=datetime(2026, 8, 1, 16, 0, tzinfo=UTC),
        species_guess=None,
        set_representative_media_path=True,
    )
    add_visit_with_media(
        isolated_repository,
        visit_id="sibling-b",
        event_id=shared_event_id,
        started_at=datetime(2026, 8, 1, 16, 0, tzinfo=UTC),
        species_guess=None,
        set_representative_media_path=True,
    )

    detail = await client.get("/api/visits/sibling-a/detail")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["visit"]["representative_media_path"] is None
    assert len(payload["sibling_visits"]) == 1
    assert payload["sibling_visits"][0]["id"] == "sibling-b"
    assert payload["sibling_visits"][0]["representative_media_path"] is None


async def test_list_media_assets_redacts_local_path(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    """Pre-Release Trust & Correctness Correction v1 (SEC-2): GET /api/media
    exposed the raw absolute server-local filesystem path to any signed-in
    Viewer -- unlike Visit-facing endpoints, which already redact it (see the
    two tests above). Legitimate access (status 200, the asset otherwise
    resolvable) must be unaffected."""

    add_graph(isolated_repository)
    add_visit_with_media(
        isolated_repository,
        visit_id="media-list-leak",
        started_at=datetime(2026, 8, 1, 17, 0, tzinfo=UTC),
        species_guess=None,
        set_representative_media_path=False,
    )

    listing = await client.get("/api/media")
    assert listing.status_code == 200
    assets = listing.json()
    assert any(asset["id"] == "media-media-list-leak" for asset in assets)
    assert all(asset["local_path"] == "" for asset in assets)


async def test_get_media_asset_redacts_local_path(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    add_graph(isolated_repository)
    add_visit_with_media(
        isolated_repository,
        visit_id="media-detail-leak",
        started_at=datetime(2026, 8, 1, 17, 0, tzinfo=UTC),
        species_guess=None,
        set_representative_media_path=False,
    )

    detail = await client.get("/api/media/media-media-detail-leak")
    assert detail.status_code == 200
    asset = detail.json()
    assert asset["id"] == "media-media-detail-leak"
    assert asset["local_path"] == ""
    # The real file still exists server-side -- redaction is API-surface
    # only, never a change to how media is actually stored or served.
    real_asset = isolated_repository.get_media_asset("media-media-detail-leak")
    assert real_asset is not None
    assert Path(real_asset.local_path).is_file()


# ---------------------------------------------------------------------------
# Event Detail evidence images for the dominant (no representative_media_path)
# Visit-creation architecture (D5/D12)
# ---------------------------------------------------------------------------


async def test_event_detail_resolves_visit_previews_without_representative_media_path(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    add_graph(isolated_repository)
    add_visit_with_media(
        isolated_repository,
        visit_id="stage7-visit",
        started_at=datetime(2026, 8, 1, 17, 0, tzinfo=UTC),
        species_guess="blue_jay",
        set_representative_media_path=False,
    )

    detail = await client.get("/api/events/event-stage7-visit/detail")
    assert detail.status_code == 200
    payload = detail.json()
    # The legacy per-Event image is genuinely absent (no Visit set it) --
    # this is exactly the scenario that used to leave the whole case file blank.
    assert payload["media_asset"] is None
    assert "stage7-visit" in payload["visit_previews"]
    preview = payload["visit_previews"]["stage7-visit"]
    assert preview["content_type"] == "image/jpeg"
    assert preview["preview_url"].endswith("/preview")


# ---------------------------------------------------------------------------
# P2m -- "ambiguous" now has a real taxonomy row like its unknown_* siblings
# ---------------------------------------------------------------------------


async def test_ambiguous_label_has_taxonomy_row(
    client: httpx.AsyncClient, isolated_repository: ProductRepository
) -> None:
    response = await client.get("/api/taxonomy/labels/ambiguous")
    assert response.status_code == 200
    payload = response.json()
    assert payload["category"] == "unknown"
    assert payload["is_reviewable"] is True


# ---------------------------------------------------------------------------
# Phase F -- cross-surface truth consistency (Journeys 1, 2, 3, 4, 6)
#
# One deterministic scenario set exercised against all four target surfaces
# (Today/dashboard, Evidence detail, Review, Bird Log) through the real HTTP
# API, proving they agree on current truth -- not just that each fix works
# in isolation.
# ---------------------------------------------------------------------------


async def add_suggestion(
    repository: ProductRepository,
    *,
    visit_id: str,
    stream_id: str,
    suggested_label: str,
    started_at: datetime,
) -> None:
    with repository.session_factory() as session:
        with session.begin():
            visit = session.get(VisitModel, visit_id)
            assert visit is not None
            session.add(
                SpeciesSuggestionModel(
                    id=f"suggestion-{visit_id}",
                    source_id=SOURCE_ID,
                    stream_id=stream_id,
                    event_id=visit.event_id,
                    visit_id=visit_id,
                    media_asset_id=f"media-{visit_id}",
                    adapter_id="fixture",
                    adapter_name="Fixture classifier",
                    suggested_label=suggested_label,
                    suggested_common_name=None,
                    suggested_scientific_name=None,
                    confidence=0.71,
                    rank=1,
                    alternatives_json="[]",
                    evidence_region_json=None,
                    status="pending",
                    created_at=started_at,
                    notes=None,
                )
            )


@pytest.fixture
async def phase_f_scenario(client: httpx.AsyncClient, isolated_repository: ProductRepository):
    """Five deterministic Visits covering every Phase F required case,
    dated "now" so they surface in Today's real (unmocked) time window."""

    add_graph(isolated_repository)
    now = datetime.now(UTC)

    # 1. Provisional: a suggestion exists, nothing reviewed yet.
    add_visit_with_media(
        isolated_repository,
        visit_id="pf-provisional",
        started_at=now - timedelta(minutes=50),
        species_guess="northern_cardinal",
        set_representative_media_path=False,
    )
    await add_suggestion(
        isolated_repository,
        visit_id="pf-provisional",
        stream_id=STREAM_ID,
        suggested_label="northern_cardinal",
        started_at=now - timedelta(minutes=50),
    )

    # 2. Correction propagation: model suggested Blue Jay (species A); human
    # corrects to Northern Cardinal (species B). Species A must not survive
    # as current truth anywhere.
    add_visit_with_media(
        isolated_repository,
        visit_id="pf-corrected",
        started_at=now - timedelta(minutes=40),
        species_guess="blue_jay",
        set_representative_media_path=False,
    )
    await review(client, "pf-corrected", "northern_cardinal")

    # 3. Uncertain/abstained: confirmed as a bird, species honestly withheld.
    add_visit_with_media(
        isolated_repository,
        visit_id="pf-unknown",
        started_at=now - timedelta(minutes=30),
        species_guess=None,
        set_representative_media_path=False,
    )
    await review(client, "pf-unknown", "unknown_bird")

    # 4. Multi-subject: two individuals, two species, one shared encounter.
    shared_event_id = "event-pf-multi-subject"
    add_visit_with_media(
        isolated_repository,
        visit_id="pf-subject-cardinal",
        event_id=shared_event_id,
        started_at=now - timedelta(minutes=20),
        species_guess="northern_cardinal",
        set_representative_media_path=False,
    )
    add_visit_with_media(
        isolated_repository,
        visit_id="pf-subject-squirrel",
        event_id=shared_event_id,
        started_at=now - timedelta(minutes=20),
        species_guess=None,
        set_representative_media_path=False,
    )
    await review(client, "pf-subject-cardinal", "northern_cardinal")
    await review(client, "pf-subject-squirrel", "squirrel")

    # 5. Audio-only: BirdNET-only encounter, never seen by a camera.
    with isolated_repository.session_factory() as session:
        with session.begin():
            audio_media_id = "media-pf-audio"
            audio_path = isolated_repository.media_root / "pf-audio.wav"
            audio_path.parent.mkdir(parents=True, exist_ok=True)
            audio_path.write_bytes(b"fixture-wav-bytes")
            session.add(
                MediaAssetModel(
                    id=audio_media_id,
                    source_id=SOURCE_ID,
                    stream_id=STREAM_ID,
                    filename="pf-audio.wav",
                    content_type="audio/wav",
                    media_type="audio",
                    local_path=str(audio_path),
                    original_filename="pf-audio.wav",
                    file_size_bytes=len(b"fixture-wav-bytes"),
                    created_at=now - timedelta(minutes=10),
                )
            )
    audio_outcome = isolated_repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID,
        media_asset_id=audio_media_id,
        detection=AcousticDetectionFacts(
            common_name="Carolina Wren",
            scientific_name=None,
            confidence=0.81,
            window_start_ms=0,
            window_end_ms=5_000,
        ),
        model_provenance={"adapter": "fixture-birdnet"},
        observed_at=now - timedelta(minutes=10),
        adapter_id="birdnet",
        adapter_name="BirdNET",
    )
    await review(client, audio_outcome.visit_id, "carolina_wren")

    return {"audio_visit_id": audio_outcome.visit_id}


async def test_today_dashboard_shows_only_corrected_truth(
    client: httpx.AsyncClient, phase_f_scenario: dict
) -> None:
    response = await client.get("/api/dashboard/summary")
    assert response.status_code == 200
    payload = response.json()
    rendered = str(payload)
    # Species A (the pre-correction model suggestion) must not survive
    # anywhere in Today's own response as if it were current truth.
    assert "blue_jay" not in rendered

    best_moment_ids = {visit["id"] for visit in payload["today"]["best_moments"]}
    # Positive proof, not just absence: the corrected/multi-subject/audio
    # Visits actually appear as today's countable animal activity (a
    # vacuously-passing "blue_jay not present" check on an empty list would
    # prove nothing).
    assert {"pf-corrected", "pf-subject-cardinal", "pf-subject-squirrel"} <= best_moment_ids

    confirmed_labels = {
        visit["reviewed_label"]
        for visit in payload["today"]["best_moments"]
        + payload["today"]["new_today"]
        + payload["today"]["recent_regulars"]
        if visit.get("reviewed_label")
    }
    assert "northern_cardinal" in confirmed_labels
    # The corrected Visit's *current* truth (species B) is present wherever
    # its reviewed_label is surfaced; nothing claims "blue_jay".
    assert "blue_jay" not in confirmed_labels


async def test_visit_detail_shows_only_corrected_truth(
    client: httpx.AsyncClient, phase_f_scenario: dict
) -> None:
    detail = await client.get("/api/visits/pf-corrected/detail")
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["visit"]["reviewed_label"] == "northern_cardinal"
    # species_guess (species A) is retained as historical model provenance --
    # doctrine requires provenance survive a correction -- but it must never
    # be presented as current truth: reviewed_label already wins by
    # construction, and the frontend's identificationBadge only reads
    # reviewed_label once present (see VisitDetailPage.tsx).
    assert payload["visit"]["species_guess"] == "blue_jay"
    assert payload["visit"]["review_status"] == "reviewed"


async def test_review_queue_reflects_all_five_scenarios_correctly(
    client: httpx.AsyncClient, phase_f_scenario: dict
) -> None:
    queue = await client.get("/api/review-queue", params={"include_reviewed": "true"})
    assert queue.status_code == 200
    by_id = {item["target_id"]: item for item in queue.json()}

    assert by_id["pf-provisional"]["review_status"] == "needs_review"
    assert by_id["pf-provisional"]["reviewed_label"] is None
    assert by_id["pf-provisional"]["suggested_label"] == "northern_cardinal"

    assert by_id["pf-corrected"]["review_status"] == "reviewed"
    assert by_id["pf-corrected"]["reviewed_label"] == "northern_cardinal"

    assert by_id["pf-unknown"]["review_status"] == "reviewed"
    assert by_id["pf-unknown"]["reviewed_label"] == "unknown_bird"

    assert by_id["pf-subject-cardinal"]["reviewed_label"] == "northern_cardinal"
    assert by_id["pf-subject-squirrel"]["reviewed_label"] == "squirrel"
    # Multi-subject: correcting one sibling must never overwrite the other.
    assert by_id["pf-subject-cardinal"]["reviewed_label"] != by_id["pf-subject-squirrel"]["reviewed_label"]

    audio_item = by_id[phase_f_scenario["audio_visit_id"]]
    assert audio_item["reviewed_label"] == "carolina_wren"
    assert audio_item["media_asset"]["media_type"] == "audio"


async def test_bird_log_reflects_all_confirmed_scenarios_honestly(
    client: httpx.AsyncClient, phase_f_scenario: dict
) -> None:
    overview = await client.get("/api/bird-log/journal")
    assert overview.status_code == 200
    labels = {item["label"]: item for item in overview.json()["labels"]}

    # Corrected truth (species B), never the pre-correction suggestion.
    assert "northern_cardinal" in labels
    assert "blue_jay" not in labels
    # Multi-subject: both individuals present as distinct confirmed species.
    assert "squirrel" in labels
    # Audio-only confirmed species appears like any other confirmed wildlife.
    assert "carolina_wren" in labels
    # Honest abstention: "unknown_bird" is confirmed-animal-present-species-
    # unresolved, a distinct concept from a named taxon (product-doctrine.md)
    # -- never fabricated into a fake species entry here.
    assert "unknown_bird" not in labels
    # Wildlife Semantic Consistency v1: still real, honestly counted --
    # never silently dropped just because it has no `labels` entry. Before
    # this fix, "pf-unknown" resolved to `VisitReviewOutcome.ambiguous` and
    # was invisible to Bird Log entirely, contradicting Today's own
    # `confirmed_species_unresolved_visit_count` for the identical Visit.
    assert overview.json()["confirmed_species_unresolved_visit_count"] == 1
    # Still-provisional Visit has no reviewed truth at all yet.
    assert not any(
        visit_id == "pf-provisional"
        for label in labels.values()
        for visit_id in [label.get("representative", {}).get("visit_id")]
    )

    cardinal_history = await client.get("/api/bird-log/journal/northern_cardinal")
    assert cardinal_history.status_code == 200
    cardinal_visit_ids = {row["visit_id"] for row in cardinal_history.json()["gallery"]["observations"]}
    assert "pf-corrected" in cardinal_visit_ids
    assert "pf-subject-cardinal" in cardinal_visit_ids

    audio_history = await client.get("/api/bird-log/journal/carolina_wren")
    assert audio_history.status_code == 200
    audio_observation = audio_history.json()["gallery"]["observations"][0]
    assert audio_observation["primary_evidence"]["content_type"] == "audio/wav"
    assert audio_observation["duration_seconds"] == pytest.approx(5.0, abs=0.01)


async def test_multi_subject_event_detail_keeps_both_subjects_distinct(
    client: httpx.AsyncClient, phase_f_scenario: dict
) -> None:
    detail = await client.get("/api/events/event-pf-multi-subject/detail")
    assert detail.status_code == 200
    payload = detail.json()
    visits_by_id = {visit["id"]: visit for visit in payload["visits"]}
    assert len(visits_by_id) == 2
    assert visits_by_id["pf-subject-cardinal"]["reviewed_label"] == "northern_cardinal"
    assert visits_by_id["pf-subject-squirrel"]["reviewed_label"] == "squirrel"
    # Each subject resolves its own distinct evidence preview.
    assert "pf-subject-cardinal" in payload["visit_previews"]
    assert "pf-subject-squirrel" in payload["visit_previews"]
