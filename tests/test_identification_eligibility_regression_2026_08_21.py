"""Identification Eligibility + Abstention v1 -- wiring-level regression
coverage.

`test_identification_eligibility.py` proves the canonical decision
boundary's own properties (pure, deterministic, real-data-grounded).  This
file proves the *wiring*: that `product_repository.py`'s real
`identify_review_queue_item` path actually consults that boundary before
and after a real (mocked) BioCLIP call, through the real API, against a
real isolated repository -- matching the harness convention already
established in `test_review_identification.py` (fixtures/helpers
intentionally duplicated here rather than cross-imported, per this
repository's existing one-file-one-harness convention; see
docs/test-repository-isolation-contract.md).

Covers the milestone's remaining mandatory items that need real repository
wiring, not just the pure function: 1 (strong evidence still suggests,
end-to-end), 2-3 (person 139/140, end-to-end), 5 (the evidence-eligibility
seam that derives real pixel dimensions from crop/media facts), 8 (a later
anomalous/abstained attempt must not downgrade an earlier valid
suggestion -- the real-architecture analog of "disagreement across good
frames," since at most one classifier-input frame exists per Visit today,
see the report), 9 (reviewed truth always overrides), 10 (Visit creation
continues when identification abstains), 11-12 (sibling/independent-Visit
isolation), 13 (same-frame evidence stays correctly attributed through to
persisted provenance).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.repository import product_repository
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.species.bioclip_adapter import (
    BIOCLIP_ADAPTER_ID,
    BIOCLIP_ADAPTER_NAME,
    BIOCLIP_CANDIDATE_FINGERPRINT_ALGORITHM,
    BIOCLIP_PREPROCESSING_CONFIG_JSON,
    BIOCLIP_PROMPT_RECIPE_ID,
    BIOCLIP_PROMPT_RECIPE_SHA256,
    BIOCLIP_RUN_TIMEOUT_SECONDS,
    BIOCLIP_SCORE_KIND,
    BioClipPrediction,
    BioClipPreparedRun,
    BioClipProvenance,
    BioClipRankedSuggestion,
)
from mockingbird.species.identification_eligibility import (
    evaluate_identification_eligibility,
)
from mockingbird.storage.models import MediaAssetModel

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_MODEL_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_LABELS_PATH", raising=False)
    monkeypatch.delenv("MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH", raising=False)
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
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def import_review_image(client: httpx.AsyncClient, *, title: str = "Eligibility regression image"):
    response = await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": title,
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Local image for identification eligibility regression.",
        },
        files={"file": ("eligibility-regression.png", b"eligibility regression image bytes", "image/png")},
    )
    assert response.status_code == 201
    return response.json()


def mark_bioclip_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    model_dir = tmp_path / "bioclip-model"
    labels_path = tmp_path / "bioclip-labels.txt"
    cache_path = tmp_path / "bioclip-embeddings.npz"
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_MODEL_PATH", str(model_dir))
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_LABELS_PATH", str(labels_path))
    monkeypatch.setenv("MOCKINGBIRD_BIOCLIP_EMBEDDING_CACHE_PATH", str(cache_path))
    monkeypatch.setattr(
        product_repository,
        "get_bioclip_status",
        lambda _config: SimpleNamespace(
            status="available",
            configured=True,
            runtime_available=True,
            detail="Mock BioCLIP is available for eligibility regression tests.",
            model_dir=str(model_dir),
            labels_path=str(labels_path),
            embedding_cache_path=str(cache_path),
            device="cpu",
            labels_sha256="a" * 64,
        ),
    )


def bioclip_prediction(*ranked: tuple[str, str | None, str | None, float]) -> BioClipPrediction:
    candidate_labels = tuple(item[0] for item in ranked)
    suggestions = tuple(
        BioClipRankedSuggestion(rank=index, label=label, common_name=common_name, scientific_name=scientific_name, score=score)
        for index, (label, common_name, scientific_name, score) in enumerate(ranked, start=1)
    )
    # Must match `product_repository._candidate_bank_sha256` exactly --
    # `_bioclip_prediction_has_complete_candidate_bank` verifies self-
    # consistency between `candidate_labels` and this hash before ever
    # reaching this milestone's own eligibility/abstention checks.
    labels_sha256 = hashlib.sha256("\n".join(candidate_labels).encode("utf-8")).hexdigest()
    return BioClipPrediction(
        suggestions=suggestions,
        provenance=BioClipProvenance(
            adapter_id=BIOCLIP_ADAPTER_ID,
            adapter_name=BIOCLIP_ADAPTER_NAME,
            model_name="BioCLIP 2 local test",
            device="cpu",
            open_clip_version="3.3.0",
            torch_version="2.13.0+cpu",
            label_count=len(candidate_labels),
            labels_sha256=labels_sha256,
            embedding_cache_sha256="b" * 64,
            model_config_sha256="c" * 64,
            model_weights_name="open_clip_model.safetensors",
            model_weights_sha256="d" * 64,
            prompt_recipe_id=BIOCLIP_PROMPT_RECIPE_ID,
            prompt_recipe_sha256=BIOCLIP_PROMPT_RECIPE_SHA256,
            score_kind=BIOCLIP_SCORE_KIND,
            calibrated=False,
        ),
        candidate_labels=candidate_labels,
        candidate_scores=tuple(item[3] for item in ranked),
    )


def bioclip_prepared_run(prediction: BioClipPrediction) -> BioClipPreparedRun:
    provenance = prediction.provenance
    return BioClipPreparedRun(
        adapter_id=provenance.adapter_id,
        adapter_name=provenance.adapter_name,
        adapter_contract_version=provenance.adapter_contract_version,
        model_name=provenance.model_name,
        architecture_id=provenance.architecture_id,
        device=provenance.device,
        candidate_labels=prediction.candidate_labels,
        candidate_count=len(prediction.candidate_labels),
        candidate_set_sha256=provenance.labels_sha256,
        candidate_fingerprint_algorithm=BIOCLIP_CANDIDATE_FINGERPRINT_ALGORITHM,
        embedding_cache_sha256=provenance.embedding_cache_sha256,
        model_config_sha256=provenance.model_config_sha256,
        model_weights_sha256=provenance.model_weights_sha256,
        model_weights_name=provenance.model_weights_name,
        model_weights_verified=False,
        prompt_recipe_id=provenance.prompt_recipe_id,
        prompt_recipe_sha256=provenance.prompt_recipe_sha256,
        preprocessing_id=provenance.preprocessing_id,
        preprocessing_sha256=provenance.preprocessing_sha256,
        preprocessing_config_json=BIOCLIP_PREPROCESSING_CONFIG_JSON,
        timeout_seconds=BIOCLIP_RUN_TIMEOUT_SECONDS,
        open_clip_version=provenance.open_clip_version,
        torch_version=provenance.torch_version,
        pillow_version="11.3.0",
        numpy_version="2.3.0",
    )


def mock_bioclip_run(monkeypatch: pytest.MonkeyPatch, prediction: BioClipPrediction) -> None:
    def load_image(**kwargs: object) -> object:
        return object()

    def run_image(image_loader: object, _config: object, top_k: int = 5, *, on_prepared: object | None = None) -> BioClipPrediction:
        assert callable(image_loader)
        if on_prepared is not None:
            on_prepared(bioclip_prepared_run(prediction))
        image_loader()
        return prediction

    monkeypatch.setattr(product_repository, "prepare_bioclip_run", lambda _config: bioclip_prepared_run(prediction))
    monkeypatch.setattr(product_repository, "_load_bioclip_input_image", load_image)
    monkeypatch.setattr(product_repository, "run_bioclip_from_image_loader", run_image)


async def deactivate_default_ignore_zone(client: httpx.AsyncClient) -> None:
    """The seeded test fixture data includes an active ignore zone
    (`zone-ignore-driveway-edge`) that would otherwise block full-frame
    classification for these plain-image-import Visits (they carry no
    activity/MegaDetector crop, so their classifier input is the whole
    frame) -- matches the same deactivation step every full-frame-path
    test in `test_review_identification.py` already performs."""

    response = await client.patch(
        "/api/zones/zone-ignore-driveway-edge", json={"is_active": False}
    )
    assert response.status_code == 200


async def identify(client: httpx.AsyncClient, visit_id: str) -> dict:
    response = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})
    assert response.status_code == 200
    return response.json()


# --- Item 5: the evidence-eligibility seam ----------------------------------


class TestClassifierInputPixelDimensionsWiring:
    """`_classifier_input_pixel_dimensions` is the exact seam between real
    crop/media facts and `evaluate_identification_eligibility`. Proving it
    derives pixel size correctly for every tier is what makes the pure
    module's own eligibility floor (test_identification_eligibility.py)
    actually apply to real evidence."""

    def test_override_tier_uses_its_own_explicit_dimensions(self) -> None:
        crop = product_repository._ReviewSpeciesCropContext(
            source="activity",
            box_normalized=product_repository.BoundingBox(x=0.1, y=0.1, width=0.2, height=0.2),
            label="Same-frame subject crop (classifier evidence)",
            classifier_input_width=250,
            classifier_input_height=180,
        )
        media_asset = MediaAssetModel(image_width=3840, image_height=2160)
        width, height = product_repository._classifier_input_pixel_dimensions(crop, media_asset)
        assert (width, height) == (250, 180)

    def test_megadetector_tier_derives_from_box_times_source_dimensions(self) -> None:
        crop = product_repository._ReviewSpeciesCropContext(
            source="megadetector",
            box_normalized=product_repository.BoundingBox(x=0.35, y=0.25, width=0.2, height=0.2),
            label="MegaDetector animal focus",
        )
        media_asset = MediaAssetModel(image_width=1000, image_height=500)
        width, height = product_repository._classifier_input_pixel_dimensions(crop, media_asset)
        assert (width, height) == (200, 100)

    def test_full_frame_tier_returns_the_full_source_size(self) -> None:
        crop = product_repository._ReviewSpeciesCropContext(
            source="full_frame",
            box_normalized=product_repository.BoundingBox(x=0.0, y=0.0, width=1.0, height=1.0),
            label="Full frame fallback",
        )
        media_asset = MediaAssetModel(image_width=3840, image_height=2160)
        width, height = product_repository._classifier_input_pixel_dimensions(crop, media_asset)
        assert (width, height) == (3840, 2160)

    def test_unknown_source_dimensions_propagate_as_unknown_not_zero(self) -> None:
        crop = product_repository._ReviewSpeciesCropContext(
            source="megadetector",
            box_normalized=product_repository.BoundingBox(x=0.35, y=0.25, width=0.2, height=0.2),
            label="MegaDetector animal focus",
        )
        media_asset = MediaAssetModel(image_width=None, image_height=None)
        width, height = product_repository._classifier_input_pixel_dimensions(crop, media_asset)
        assert (width, height) == (None, None)
        # And that "unknown" correctly does not block eligibility -- see
        # test_identification_eligibility.py's own dedicated proof; this
        # confirms the wiring feeds it the same honest `None`, not a guess.
        assert evaluate_identification_eligibility(
            classifier_input_width=width, classifier_input_height=height
        ).eligible is True

    def test_a_real_tiny_derived_crop_is_correctly_flagged_ineligible(self) -> None:
        crop = product_repository._ReviewSpeciesCropContext(
            source="megadetector",
            box_normalized=product_repository.BoundingBox(x=0.5, y=0.5, width=0.01, height=0.01),
            label="MegaDetector animal focus",
        )
        media_asset = MediaAssetModel(image_width=1000, image_height=500)
        width, height = product_repository._classifier_input_pixel_dimensions(crop, media_asset)
        assert (width, height) == (10, 5)
        decision = evaluate_identification_eligibility(
            classifier_input_width=width, classifier_input_height=height
        )
        assert decision.eligible is False
        assert decision.reason_code == "evidence_below_resolution_floor"


# --- End-to-end: strong evidence, person hard negatives ---------------------


async def test_strong_genuine_bird_evidence_still_produces_a_suggestion(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Item 1: a real, well-supported classification is not collateral
    damage from this milestone."""

    await deactivate_default_ignore_zone(client)
    imported = await import_review_image(client, title="Strong cardinal evidence")
    visit_id = imported["visit"]["id"]
    mark_bioclip_available(monkeypatch, tmp_path)
    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(
            ("northern cardinal (Cardinalis cardinalis)", None, None, 0.8906447291374207),
            ("brown thrasher (Toxostoma rufum)", None, None, 0.06705698370933533),
        ),
    )

    result = await identify(client, visit_id)

    assert result["identification"]["status"] == "suggestion_created"
    assert result["species_suggestion"]["suggested_label"] == "northern_cardinal"
    assert result["species_suggestion"]["evidence_region"]["identification_policy"]["abstained"] is False


async def test_visit_139_real_score_produces_no_forced_species_name(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Item 2. Real score from docs/person-background-false-positive-
    attribution-v1-report.md S2 (brown_thrasher, 0.5275). No person
    recognition/human-tracking/face-detection is implied -- only that
    species identification is unsupported."""

    await deactivate_default_ignore_zone(client)
    imported = await import_review_image(client, title="Visit 139 real score, person passage")
    visit_id = imported["visit"]["id"]
    mark_bioclip_available(monkeypatch, tmp_path)
    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(("brown thrasher (Toxostoma rufum)", None, None, 0.5275)),
    )

    result = await identify(client, visit_id)

    assert result["identification"]["status"] == "identification_uncertain"
    assert result["identification"]["unavailable_reason"] == "bioclip_identification_ambiguous"
    assert result["species_suggestion"] is None
    assert result["created_suggestion_ids"] == []
    assert result["creates_truth"] is False


async def test_visit_140_real_score_produces_no_forced_species_name(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Item 3. Real score from the same report (red_bellied_woodpecker,
    0.5986) -- Visit 140's own real detector max_confidence (0.877)
    exceeded every genuine bird Visit that session, which is exactly why a
    visual/species-layer signal, not a detector-confidence one, is what
    this milestone adds."""

    await deactivate_default_ignore_zone(client)
    imported = await import_review_image(client, title="Visit 140 real score, person passage")
    visit_id = imported["visit"]["id"]
    mark_bioclip_available(monkeypatch, tmp_path)
    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(("red bellied woodpecker (Melanerpes carolinus)", None, None, 0.5986)),
    )

    result = await identify(client, visit_id)

    assert result["identification"]["status"] == "identification_uncertain"
    assert result["identification"]["unavailable_reason"] == "bioclip_identification_ambiguous"
    assert result["species_suggestion"] is None


# --- Item 10: ordinary Visit creation/review continues when abstained ------


async def test_visit_remains_a_valid_reviewable_candidate_when_identification_abstains(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Species-identification abstention must never mean Visit rejection.
    The Visit stays exactly as reviewable, and exactly as much a real
    animal/Visit candidate, as before the (declined) identification
    attempt."""

    await deactivate_default_ignore_zone(client)
    imported = await import_review_image(client, title="Visit stays reviewable despite abstention")
    visit_id = imported["visit"]["id"]
    before = await client.get("/api/review-queue")
    assert any(item["visit_id"] == visit_id for item in before.json())

    mark_bioclip_available(monkeypatch, tmp_path)
    mock_bioclip_run(monkeypatch, bioclip_prediction(("mourning dove (Zenaida macroura)", None, None, 0.4)))
    result = await identify(client, visit_id)
    assert result["identification"]["status"] == "identification_uncertain"

    after = await client.get("/api/review-queue")
    assert any(item["visit_id"] == visit_id for item in after.json())
    detail = await client.get(f"/api/visits/{visit_id}")
    assert detail.status_code == 200
    assert detail.json()["review_status"] == "needs_review"
    # unchanged from `import_review_image`'s own seeded default -- never
    # silently replaced by an abstained attempt.
    assert detail.json()["species_guess"] == "unknown_bird"


# --- Item 9: reviewed human truth always overrides provisional state -------


async def test_reviewed_label_is_never_overwritten_by_a_later_suggestion(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A strong, eligible, non-abstained provisional suggestion still sets
    `species_guess` on an unreviewed Visit -- but once a human submits an
    explicit correction, that reviewed truth is what stands, never the
    earlier provisional guess. (Separately, and more strongly: once a
    Visit is reviewed it no longer even surfaces as a Review Queue item at
    all, so a *later* identify call correctly reports
    `missing_review_candidate` rather than ever reaching model inference --
    verified directly below.)"""

    await deactivate_default_ignore_zone(client)
    imported = await import_review_image(client, title="Reviewed truth outranks provisional suggestion")
    visit_id = imported["visit"]["id"]

    mark_bioclip_available(monkeypatch, tmp_path)
    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(("house finch (Haemorhous mexicanus)", None, None, 0.95)),
    )
    before_review = await identify(client, visit_id)
    assert before_review["identification"]["status"] == "suggestion_created"
    before_detail = (await client.get(f"/api/visits/{visit_id}")).json()
    assert before_detail["species_guess"] == "house_finch"

    correction = await client.post(
        "/api/review-labels",
        json={
            "review_origin": "human",
            "target_type": "visit",
            "target_id": visit_id,
            "label": "carolina_wren",
        },
    )
    assert correction.status_code == 201

    after_detail = (await client.get(f"/api/visits/{visit_id}")).json()
    assert after_detail["reviewed_label"] == "carolina_wren"
    assert after_detail["review_status"] == "reviewed"

    # A later identify call cannot silently reintroduce a provisional guess
    # over reviewed truth -- the Visit is no longer a review candidate at
    # all once reviewed.
    late_result = await identify(client, visit_id)
    assert late_result["identification"]["unavailable_reason"] == "missing_review_candidate"
    final_detail = (await client.get(f"/api/visits/{visit_id}")).json()
    assert final_detail["reviewed_label"] == "carolina_wren"


# --- Item 8: a later abstained attempt never downgrades an earlier valid --
# --- suggestion (the real-architecture analog of frame disagreement) ------


async def test_a_later_abstained_reattempt_does_not_downgrade_an_earlier_valid_suggestion(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """At most one classifier-input frame exists per Visit today (Same-
    Frame Species Evidence v1's own explicit design), so true multi-frame
    disagreement cannot be exercised directly -- but a manual "identify
    again" re-attempt is a real, reachable path, and an anomalous/abstained
    result from it must not silently erase or supersede a Visit's existing
    good suggestion. `_supersede_pending_bioclip_suggestions` (which marks
    a prior suggestion `superseded`) is only ever reached on the *success*
    path in `_identify_review_queue_with_bioclip`, strictly after this
    milestone's own abstention check -- proven here end-to-end, not just by
    reading the code."""

    await deactivate_default_ignore_zone(client)
    imported = await import_review_image(client, title="Later abstained re-attempt")
    visit_id = imported["visit"]["id"]
    mark_bioclip_available(monkeypatch, tmp_path)

    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(
            ("northern cardinal (Cardinalis cardinalis)", None, None, 0.9),
            ("brown thrasher (Toxostoma rufum)", None, None, 0.03),
        ),
    )
    first = await identify(client, visit_id)
    assert first["identification"]["status"] == "suggestion_created"
    first_suggestion_id = first["species_suggestion"]["id"]

    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(("blue jay (Cyanocitta cristata)", None, None, 0.4)),
    )
    second = await identify(client, visit_id)
    assert second["identification"]["status"] == "identification_uncertain"
    assert second["created_suggestion_ids"] == []
    # The response's `species_suggestion` reflects the Visit's current
    # state, not "what this call created" -- so it correctly still shows
    # the earlier real suggestion, unchanged, rather than nothing.
    assert second["species_suggestion"]["id"] == first_suggestion_id

    suggestions = (
        await client.get("/api/species-suggestions", params={"visit_id": visit_id})
    ).json()["species_suggestions"]
    assert [item["id"] for item in suggestions] == [first_suggestion_id]
    assert suggestions[0]["status"] == "pending"  # never marked superseded
    detail = (await client.get(f"/api/visits/{visit_id}")).json()
    assert detail["species_guess"] == "northern_cardinal"  # unchanged


# --- Items 11-12: independent Visits, independent outcomes -----------------


async def test_independent_visits_retain_independent_eligibility_and_suggestions(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Neither `identification_eligibility`'s pure functions nor
    `_apply_species_guess_from_suggestion` hold any cross-Visit state, so
    this property holds for any two Visits -- including genuine
    concurrent-sibling Visits from Multi-Subject Visit Assembly, which are
    independently-created rows through this exact same per-Visit path."""

    await deactivate_default_ignore_zone(client)
    strong_visit = (await import_review_image(client, title="Sibling A: strong evidence"))["visit"]["id"]
    weak_visit = (await import_review_image(client, title="Sibling B: weak evidence"))["visit"]["id"]
    mark_bioclip_available(monkeypatch, tmp_path)

    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(
            ("house finch (Haemorhous mexicanus)", None, None, 0.95),
            ("purple finch (Haemorhous purpureus)", None, None, 0.03),
        ),
    )
    strong_result = await identify(client, strong_visit)

    mock_bioclip_run(
        monkeypatch,
        bioclip_prediction(("house finch (Haemorhous mexicanus)", None, None, 0.4)),
    )
    weak_result = await identify(client, weak_visit)

    assert strong_result["identification"]["status"] == "suggestion_created"
    assert strong_result["species_suggestion"]["suggested_label"] == "house_finch"
    assert weak_result["identification"]["status"] == "identification_uncertain"
    assert weak_result["species_suggestion"] is None

    strong_detail = (await client.get(f"/api/visits/{strong_visit}")).json()
    weak_detail = (await client.get(f"/api/visits/{weak_visit}")).json()
    assert strong_detail["species_guess"] == "house_finch"
    assert weak_detail["species_guess"] == "unknown_bird"  # unchanged, not silently replaced


# --- Item 13: same-frame classifier evidence stays correctly attributed ----


def test_same_frame_crop_provenance_and_identification_policy_coexist_honestly(
    isolated_repository: ProductRepository,
) -> None:
    """`_bioclip_species_suggestion_payload` must record both *what pixels
    were actually classified* (`classifier_input`, from Same-Frame Species
    Evidence v1) and *why this policy trusted the result*
    (`identification_policy`, this milestone) on the same persisted
    suggestion, without either clobbering the other -- a reviewer must
    still be able to tell "this suggestion came from the exact same-frame
    crop, at this tier, clearing this score/margin floor" from one record."""

    with isolated_repository.session_factory() as session:
        pack_model, _warning, _selected = (
            isolated_repository._effective_species_candidate_pack_for_stream(
                session, STREAM_ID
            )
        )
        candidate_pack = isolated_repository._species_candidate_pack_from_model(
            session, pack_model
        )

    crop = product_repository._ReviewSpeciesCropContext(
        source="activity",
        box_normalized=product_repository.BoundingBox(x=0.3, y=0.4, width=0.15, height=0.15),
        label="Same-frame subject crop (classifier evidence)",
        classifier_input_media_asset_id="media-same-frame-001",
        classifier_input_local_path="/tmp/same-frame-001.jpg",
        classifier_input_size_bytes=1024,
        classifier_input_mtime_ns=0,
        classifier_input_content_type="image/jpeg",
        classifier_input_source_width=1920,
        classifier_input_source_height=1440,
        classifier_input_width=288,
        classifier_input_height=216,
        classifier_input_type="same_frame_crop",
        classifier_input_same_frame=True,
        classifier_input_crop_method="exact_frame_subject_box_padded",
        classifier_input_selection_reason="Subject box proven same_frame=True for this exact media asset.",
    )
    run_context = product_repository._ReviewSpeciesRunContext(
        target_type="visit",
        target_id="visit-same-frame-001",
        local_path=crop.classifier_input_local_path,
        media_file_size_bytes=crop.classifier_input_size_bytes,
        media_file_mtime_ns=0,
        content_type="image/jpeg",
        source_id=SOURCE_ID,
        stream_id=STREAM_ID,
        event_id="event-same-frame-001",
        visit_id="visit-same-frame-001",
        media_asset_id="media-review-001",
        motion_evidence_id=None,
        zone_id=FEEDER_ZONE_ID,
        crop=crop,
        candidate_pack=candidate_pack,
    )
    prediction = bioclip_prediction(
        ("house finch (Haemorhous mexicanus)", None, None, 0.95),
        ("purple finch (Haemorhous purpureus)", None, None, 0.03),
    )
    crop_provenance = product_repository._initial_bioclip_crop_provenance(crop)
    tier = product_repository.classifier_input_tier(
        classifier_input_type=crop.classifier_input_type, crop_source=crop.source
    )
    abstention = product_repository.evaluate_classification_abstention(
        tuple(
            product_repository.IdentificationScoredCandidate(label=c.label, score=c.score)
            for c in prediction.suggestions
        ),
        tier=tier,
    )
    assert abstention.abstained is False
    crop_provenance["identification_policy"] = {
        "policy_version": product_repository.IDENTIFICATION_ELIGIBILITY_POLICY_VERSION,
        "tier": abstention.tier,
        "top1_label": abstention.top1_label,
        "top1_score": abstention.top1_score,
        "margin": abstention.margin,
        "score_floor": abstention.score_floor,
        "margin_floor": abstention.margin_floor,
        "abstained": abstention.abstained,
    }

    payload = product_repository._bioclip_species_suggestion_payload(
        prediction, run_context=run_context, crop_provenance=crop_provenance, request_notes=None,
    )

    assert payload is not None
    region = payload.evidence_region
    # Same-Frame Species Evidence v1's own attribution survives unchanged.
    assert region["classifier_input"]["input_type"] == "same_frame_crop"
    assert region["classifier_input"]["same_frame"] is True
    # This milestone's own attribution sits alongside it, not instead of it.
    assert region["identification_policy"]["tier"] == "subject_focused"
    assert region["identification_policy"]["abstained"] is False
    assert region["identification_policy"]["policy_version"] == "identification-eligibility-v1"
    assert region["identification_policy"]["top1_score"] == pytest.approx(0.95)
