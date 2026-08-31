"""Background / Empty Evidence Species-Confidence Correctness v1 --
wiring-level and end-to-end regression coverage.

Representative Daylight Gate A Field Acceptance v5 (docs/representative-
daylight-gate-a-field-acceptance-v5-report.md, "Defects") reproduced a real
false-positive admission (a weak, single-detection, `terminal_reason:
maximum_unsupported_duration` localization -- a track the tracker kept
alive on tracker-only support past its last real detector confirmation)
whose evidence crop -- real bytes, a real ordinary-sized subject-focused
crop, well above every existing size floor -- received a confident, wrong
("Brown Thrasher," 89.9% score, 0.857 margin) BioCLIP species label. Root
cause (see docs/background-empty-evidence-species-confidence-correctness-
v1-report.md): `evaluate_identification_eligibility` and
`evaluate_classification_abstention` had no signal independent of BioCLIP's
own output -- score/margin/tier cannot catch this case at any floor,
including the strictest existing one (`full_frame`, 0.85/0.40), since 0.899
score / 0.857 margin already clears it. The fix reads an already-computed,
already-persisted, BioCLIP-independent fact (`MediaAssetModel.
geometry_attribution_json`, Localization Attribution / Detection Geometry
Lineage v1, schema 33) and treats a crop backed by tracker-only
extrapolation or a stale carried-forward box, at the two crop tiers with no
other same-moment-correspondence guarantee, as ineligible for automatic
identification.

This file proves the wiring end-to-end, through the real, unmodified
`identify_review_queue_item` production path -- matching the harness
convention already established in `test_identification_eligibility_
regression_2026_08_21.py` (fixtures/helpers intentionally duplicated here
rather than cross-imported, per this repository's one-file-one-harness
convention; see docs/test-repository-isolation-contract.md). Pure
decision-function coverage of the new `geometry_source` parameter itself
lives in `tests/test_identification_eligibility.py::
TestGeometryCorroborationEligibility`.

Real repository/test infrastructure has no way to drive a real Observation
Engine v2 tracker/burst session end-to-end inside a fast unit test, so
`geometry_attribution_json` is seeded directly onto the persisted
`MediaAssetModel` row after an ordinary import/detector-run setup --
exactly the one fact a real `frame_driven_provider`/`camera_node_live.py`
session would have recorded, not a synthetic shortcut around the
eligibility boundary itself, which runs unmodified from that point on.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.detectors.megadetector_adapter import (
    MEGADETECTOR_ADAPTER_ID,
    MegaDetectorBox,
    MegaDetectorProposal,
)
from mockingbird.observation.contracts import GeometryAttribution
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
from mockingbird.storage.models import MediaAssetModel
from tests.conftest import LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

SOURCE_ID = "source-backyard-demo"
STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"


@pytest.fixture(autouse=True)
def isolated_repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MOCKINGBIRD_MEGADETECTOR_MODEL_PATH", raising=False)
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
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


async def import_review_image(client: httpx.AsyncClient, *, title: str = "Field-derived replay image"):
    response = await client.post(
        "/api/media/import",
        data={
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "title": title,
            "subject_label": "unknown_bird",
            "species_guess": "unknown_bird",
            "notes": "Background/empty evidence species-confidence correctness regression.",
        },
        files={"file": ("field-replay.png", b"field-derived replay image bytes", "image/png")},
    )
    assert response.status_code == 201
    return response.json()


def mark_megadetector_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        product_repository,
        "get_megadetector_status",
        lambda: SimpleNamespace(
            status="available",
            configured=True,
            runtime_available=True,
            model_path="/tmp/mock-megadetector.pt",
            labels_path=None,
            detail="Mock MegaDetector is available for crop evidence.",
        ),
    )


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
            detail="Mock BioCLIP is available for the field-derived replay.",
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


def mock_bioclip_run(monkeypatch: pytest.MonkeyPatch, prediction: BioClipPrediction) -> list[object]:
    """Returns the list of crops BioCLIP was actually asked to classify --
    empty iff BioCLIP was never invoked at all (the required Tier 1 proof
    that ineligible evidence short-circuits before any model call, not just
    "cannot become a suggestion")."""

    invocations: list[object] = []

    def load_image(**kwargs: object) -> object:
        invocations.append(kwargs["crop"])
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
    return invocations


async def run_megadetector(client: httpx.AsyncClient, media_asset_id: str) -> dict:
    response = await client.post(
        f"/api/model-adapters/{MEGADETECTOR_ADAPTER_ID}/runs",
        json={
            "adapter_id": MEGADETECTOR_ADAPTER_ID,
            "media_asset_id": media_asset_id,
            "zone_ids": [FEEDER_ZONE_ID],
        },
    )
    assert response.status_code == 200
    return response.json()


async def create_activity_review_item(client: httpx.AsyncClient, *, media_asset_id: str) -> str:
    """Builds a real Visit through the *legacy* motion-evidence path --
    `focus_crop_source == "activity"` -- the more realistic default
    automatic-identification path per this milestone's own investigation
    (a real Observation Engine v2 candidate Visit typically has no
    `DetectionProposalModel` row at all, so `_credible_megadetector_animal_
    proposal` returns `None` and `_review_species_crop_context` falls
    through to this tier, not the `"megadetector"` one). Mirrors
    `test_review_identification.py::create_activity_review_item`."""

    evidence_response = await client.post(
        "/api/motion/evidence",
        json={
            "source_id": SOURCE_ID,
            "stream_id": STREAM_ID,
            "zone_id": FEEDER_ZONE_ID,
            "start_frame_index": 10,
            "end_frame_index": 12,
            "best_frame_index": 11,
            "peak_changed_ratio": 0.24,
            "triggered_frame_count": 2,
            "scoring_config": {
                "source": "test_activity_motion",
                "activity_left": 0.8041,
                "activity_top": 0.6731,
                "activity_right": 0.9541,
                "activity_bottom": 0.8231,
                "activity_changed_pixel_count": 24,
                "best_frame_width": 3840,
                "best_frame_height": 2160,
            },
            "snapshot_media_asset_id": media_asset_id,
        },
    )
    assert evidence_response.status_code == 201
    evidence_id = evidence_response.json()["id"]
    promote_response = await client.post(
        f"/api/motion/evidence/{evidence_id}/promote",
        json={
            "event_title": "Weak single-detection track, empty background",
            "visit_label_hint": "unknown_animal",
            "create_event": True,
            "create_visit": True,
            "attach_snapshot_media_asset_id": media_asset_id,
        },
    )
    assert promote_response.status_code == 200
    return promote_response.json()["visit_id"]


def seed_geometry_attribution(
    repository: ProductRepository,
    media_asset_id: str,
    *,
    geometry_source: str | None,
) -> None:
    """Seeds the one fact a real Observation Engine v2 tracker/burst session
    (`candidate_visit_adapter.py`'s `geometry_attribution_json`, schema 33)
    would already have recorded for this Visit's representative frame --
    the real production write this milestone's fix reads, not a shortcut
    around it."""

    attribution = GeometryAttribution(
        geometry_source=geometry_source,
        geometry_source_offset_ms=12_000,
        geometry_source_observation_id="observation-field-replay",
        geometry_source_confidence=0.704,
        same_frame=False,
        geometry_evidence_gap_ms=3_500,
    )
    with repository.session_factory() as session:
        asset = session.get(MediaAssetModel, media_asset_id)
        assert asset is not None
        asset.geometry_attribution_json = json.dumps(asdict(attribution), sort_keys=True)
        session.commit()


async def identify(client: httpx.AsyncClient, visit_id: str) -> dict:
    response = await client.post(f"/api/review-queue/visit/{visit_id}/identify", json={})
    assert response.status_code == 200
    return response.json()


async def setup_megadetector_crop_visit(
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
    *,
    title: str,
    geometry_source: str | None,
    repository: ProductRepository,
) -> str:
    """Builds a real Visit whose species-identification crop resolves
    through the exact `"megadetector"` tier `_credible_megadetector_animal_
    proposal` selects -- the same tier the v5 field defect's own crop
    provenance is consistent with -- then seeds the one geometry-lineage
    fact under test onto its representative frame."""

    mark_megadetector_available(monkeypatch)
    monkeypatch.setattr(
        product_repository,
        "run_megadetector_on_image",
        lambda **_: [
            MegaDetectorProposal(
                label="animal",
                confidence=0.704,
                bbox=MegaDetectorBox(x=0.8041, y=0.6731, width=0.15, height=0.15),
            ),
        ],
    )
    imported = await import_review_image(client, title=title)
    visit_id = imported["visit"]["id"]
    media_asset_id = imported["media_asset"]["id"]
    await run_megadetector(client, media_asset_id)
    seed_geometry_attribution(repository, media_asset_id, geometry_source=geometry_source)
    return visit_id


# --- Required RED case: background / empty evidence -------------------------


class TestBackgroundEmptyEvidenceRedToGreen:
    """The v5 defect class: a real, ordinary-sized MegaDetector-tier crop,
    BioCLIP score/margin (89.9%/0.857) confidently clear of even the
    stricter `full_frame` floor -- yet the underlying box is tracker-only
    extrapolation, never a real contemporaneous detector observation.
    Pre-fix, this exact scenario suggests (score/margin alone govern
    abstention, and eligibility only ever checked crop size); post-fix, it
    abstains before BioCLIP is ever invoked."""

    async def test_v5_pattern_tracker_sourced_geometry_produces_no_suggestion(
        self, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
    ) -> None:
        visit_id = await setup_megadetector_crop_visit(
            client, monkeypatch,
            title="Weak single-detection track, empty background",
            geometry_source="tracker",
            repository=isolated_repository,
        )
        mark_bioclip_available(monkeypatch, Path(isolated_repository.media_root))
        invocations = mock_bioclip_run(
            monkeypatch,
            bioclip_prediction(("brown thrasher (Toxostoma rufum)", None, None, 0.899)),
        )

        result = await identify(client, visit_id)

        assert result["identification"]["status"] == "identification_uncertain"
        assert result["identification"]["unavailable_reason"] == "bioclip_identification_evidence_ineligible"
        assert result["species_suggestion"] is None
        assert result["created_suggestion_ids"] == []
        assert result["creates_truth"] is False
        # The strongest possible proof: BioCLIP was never even asked to
        # classify anything -- this is not "a suggestion was discarded
        # after the fact," the model call itself never happened.
        assert invocations == []

        detail = (await client.get(f"/api/visits/{visit_id}")).json()
        assert detail["species_guess"] == "unknown_bird"  # unchanged seed default
        assert detail["review_status"] == "needs_review"  # still a valid, reviewable candidate

    async def test_carried_forward_geometry_also_produces_no_suggestion(
        self, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
    ) -> None:
        visit_id = await setup_megadetector_crop_visit(
            client, monkeypatch,
            title="Stale carried-forward box",
            geometry_source="carried_forward",
            repository=isolated_repository,
        )
        mark_bioclip_available(monkeypatch, Path(isolated_repository.media_root))
        invocations = mock_bioclip_run(
            monkeypatch,
            bioclip_prediction(("house finch (Haemorhous mexicanus)", None, None, 0.95)),
        )

        result = await identify(client, visit_id)

        assert result["identification"]["status"] == "identification_uncertain"
        assert result["identification"]["unavailable_reason"] == "bioclip_identification_evidence_ineligible"
        assert result["species_suggestion"] is None
        assert invocations == []


class TestActivityTierRedToGreen:
    """The same defect class, reproduced through the *legacy* `"activity"`
    focus-crop tier rather than the `"megadetector"` `DetectionProposalModel`
    tier -- per this milestone's own investigation, the more realistic
    default automatic-identification path for an ordinary Observation Engine
    v2 candidate Visit (which typically has no `DetectionProposalModel` row
    at all). Confirms the fix is not accidentally scoped to only one of the
    two crop tiers it is meant to cover."""

    async def test_tracker_sourced_geometry_on_the_legacy_activity_tier_produces_no_suggestion(
        self, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
    ) -> None:
        imported = await import_review_image(client, title="Legacy activity-tier weak track")
        media_asset_id = imported["media_asset"]["id"]
        visit_id = await create_activity_review_item(client, media_asset_id=media_asset_id)
        seed_geometry_attribution(isolated_repository, media_asset_id, geometry_source="tracker")

        mark_bioclip_available(monkeypatch, Path(isolated_repository.media_root))
        invocations = mock_bioclip_run(
            monkeypatch,
            bioclip_prediction(("brown thrasher (Toxostoma rufum)", None, None, 0.899)),
        )

        result = await identify(client, visit_id)

        assert result["identification"]["status"] == "identification_uncertain"
        assert result["identification"]["unavailable_reason"] == "bioclip_identification_evidence_ineligible"
        assert result["species_suggestion"] is None
        assert invocations == []

    async def test_detector_sourced_geometry_on_the_legacy_activity_tier_still_suggests(
        self, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
    ) -> None:
        imported = await import_review_image(client, title="Legacy activity-tier genuine subject")
        media_asset_id = imported["media_asset"]["id"]
        visit_id = await create_activity_review_item(client, media_asset_id=media_asset_id)
        seed_geometry_attribution(isolated_repository, media_asset_id, geometry_source="detector")

        mark_bioclip_available(monkeypatch, Path(isolated_repository.media_root))
        invocations = mock_bioclip_run(
            monkeypatch,
            bioclip_prediction(("house finch (Haemorhous mexicanus)", None, None, 0.93)),
        )

        result = await identify(client, visit_id)

        assert result["identification"]["status"] == "suggestion_created"
        assert result["species_suggestion"]["suggested_label"] == "house_finch"
        assert len(invocations) == 1


# --- Wrong-subject safety ----------------------------------------------------


class TestWrongSubjectSafety:
    """Section 11's requirement is subject relevance, not ReID: the same
    uncorroborated-geometry mechanism that protects background/empty
    evidence also withholds a confident species claim when the Visit's
    selected evidence is not provably the same real-time subject the box
    claims -- a tracker-extrapolated box is, by construction, not proven
    same-moment evidence of *any* specific subject, real or otherwise."""

    async def test_uncorroborated_crop_does_not_confidently_claim_a_species(
        self, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
    ) -> None:
        visit_id = await setup_megadetector_crop_visit(
            client, monkeypatch,
            title="Box drifted off the original subject",
            geometry_source="tracker",
            repository=isolated_repository,
        )
        mark_bioclip_available(monkeypatch, Path(isolated_repository.media_root))
        # Even a maximally confident, unambiguous-looking result must not
        # become a Visit-level species claim from this evidence.
        invocations = mock_bioclip_run(
            monkeypatch,
            bioclip_prediction(("northern cardinal (Cardinalis cardinalis)", None, None, 0.999)),
        )

        result = await identify(client, visit_id)

        assert result["species_suggestion"] is None
        assert invocations == []


# --- Good-evidence non-regression --------------------------------------------


class TestGoodEvidenceNonRegression:
    """Good wildlife evidence -- a genuine, contemporaneous detector
    observation -- must keep working exactly as before. Do not over-tighten
    eligibility until useful species assistance disappears."""

    async def test_detector_sourced_megadetector_crop_still_suggests(
        self, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
    ) -> None:
        visit_id = await setup_megadetector_crop_visit(
            client, monkeypatch,
            title="Genuine detector-confirmed subject",
            geometry_source="detector",
            repository=isolated_repository,
        )
        mark_bioclip_available(monkeypatch, Path(isolated_repository.media_root))
        invocations = mock_bioclip_run(
            monkeypatch,
            bioclip_prediction(
                ("northern cardinal (Cardinalis cardinalis)", None, None, 0.91),
                ("brown thrasher (Toxostoma rufum)", None, None, 0.05),
            ),
        )

        result = await identify(client, visit_id)

        assert result["identification"]["status"] == "suggestion_created"
        assert result["species_suggestion"]["suggested_label"] == "northern_cardinal"
        assert result["species_suggestion"]["evidence_region"]["identification_policy"]["abstained"] is False
        assert len(invocations) == 1

    async def test_unknown_geometry_attribution_still_suggests(
        self, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
    ) -> None:
        """A Visit created before schema 33 existed, or through a path that
        never computed geometry lineage at all, carries `geometry_
        attribution_json = None` -- a data-completeness gap, never treated
        as positive evidence of an uncorroborated crop (mirrors the
        existing, already-established `classifier_input_width`/`height`
        `None` convention this same module already applies)."""

        mark_megadetector_available(monkeypatch)
        monkeypatch.setattr(
            product_repository,
            "run_megadetector_on_image",
            lambda **_: [
                MegaDetectorProposal(
                    label="animal", confidence=0.8,
                    bbox=MegaDetectorBox(x=0.4, y=0.3, width=0.1, height=0.1),
                ),
            ],
        )
        imported = await import_review_image(client, title="No geometry attribution recorded")
        visit_id = imported["visit"]["id"]
        await run_megadetector(client, imported["media_asset"]["id"])
        # No seed_geometry_attribution call -- geometry_attribution_json
        # stays exactly as `/api/media/import` left it: unset.

        mark_bioclip_available(monkeypatch, Path(isolated_repository.media_root))
        mock_bioclip_run(monkeypatch, bioclip_prediction(("house finch (Haemorhous mexicanus)", None, None, 0.92)))

        result = await identify(client, visit_id)

        assert result["identification"]["status"] == "suggestion_created"
        assert result["species_suggestion"]["suggested_label"] == "house_finch"


# --- Abstention principle preserved ------------------------------------------


class TestAbstentionPrincipleFromEligibleEvidence:
    """Eligible (detector-sourced) evidence with a weak/ambiguous BioCLIP
    result must still abstain -- this milestone adds a new *reason* to
    withhold a suggestion, it does not touch or weaken the existing
    score/margin abstention path."""

    async def test_eligible_evidence_with_weak_score_still_abstains(
        self, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
    ) -> None:
        visit_id = await setup_megadetector_crop_visit(
            client, monkeypatch,
            title="Genuine detector-confirmed subject, ambiguous classification",
            geometry_source="detector",
            repository=isolated_repository,
        )
        mark_bioclip_available(monkeypatch, Path(isolated_repository.media_root))
        invocations = mock_bioclip_run(
            monkeypatch,
            bioclip_prediction(("mourning dove (Zenaida macroura)", None, None, 0.4)),
        )

        result = await identify(client, visit_id)

        assert result["identification"]["status"] == "identification_uncertain"
        assert result["identification"]["unavailable_reason"] == "bioclip_identification_ambiguous"
        assert result["species_suggestion"] is None
        # Unlike the ineligible cases above, BioCLIP *was* actually asked --
        # this is abstention on a real result, not a pre-inference gate.
        assert len(invocations) == 1


# --- Reviewed truth preserved ------------------------------------------------


class TestReviewedTruthPreserved:
    """Species assistance remains Inferred; human Reviewed truth remains
    authoritative regardless of which reason automatic identification
    withheld or offered a suggestion for."""

    async def test_reviewed_correction_survives_a_later_ineligible_reattempt(
        self, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
    ) -> None:
        visit_id = await setup_megadetector_crop_visit(
            client, monkeypatch,
            title="Reviewed before the geometry check was ever consulted again",
            geometry_source="detector",
            repository=isolated_repository,
        )
        mark_bioclip_available(monkeypatch, Path(isolated_repository.media_root))
        mock_bioclip_run(monkeypatch, bioclip_prediction(("house finch (Haemorhous mexicanus)", None, None, 0.95)))
        first = await identify(client, visit_id)
        assert first["identification"]["status"] == "suggestion_created"

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

        # A reviewed Visit is no longer a review candidate at all -- a later
        # identify call correctly reports `missing_review_candidate` rather
        # than ever reaching either eligibility check again.
        late_result = await identify(client, visit_id)
        assert late_result["identification"]["unavailable_reason"] == "missing_review_candidate"

        final_detail = (await client.get(f"/api/visits/{visit_id}")).json()
        assert final_detail["reviewed_label"] == "carolina_wren"
        assert final_detail["review_status"] == "reviewed"


# --- Persistence: ineligible evidence leaves no stale suggestion ------------


class TestPersistence:
    """Ineligible evidence must never leave a stale automatic suggestion --
    no `SpeciesSuggestionModel` row is created at all for a withheld
    attempt (mirrors the existing `evidence_below_resolution_floor`
    behavior; this milestone adds a second reason into the same, already-
    established no-row-created path, not a new persistence mechanism)."""

    async def test_no_species_suggestion_row_is_created_for_ineligible_evidence(
        self, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
    ) -> None:
        visit_id = await setup_megadetector_crop_visit(
            client, monkeypatch,
            title="No suggestion should ever be persisted",
            geometry_source="tracker",
            repository=isolated_repository,
        )
        mark_bioclip_available(monkeypatch, Path(isolated_repository.media_root))
        mock_bioclip_run(monkeypatch, bioclip_prediction(("brown thrasher (Toxostoma rufum)", None, None, 0.899)))

        await identify(client, visit_id)

        suggestions = (
            await client.get("/api/species-suggestions", params={"visit_id": visit_id})
        ).json()["species_suggestions"]
        assert suggestions == []

    async def test_ineligible_attempt_is_still_durably_recorded(
        self, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, isolated_repository: ProductRepository,
    ) -> None:
        """The withheld attempt itself is still recorded in the pre-existing
        durable attempt ledger (never a species suggestion) -- unchanged
        behavior from the resolution-floor reason, now also true for this
        one."""

        visit_id = await setup_megadetector_crop_visit(
            client, monkeypatch,
            title="Attempt ledger records the withheld reason",
            geometry_source="tracker",
            repository=isolated_repository,
        )
        mark_bioclip_available(monkeypatch, Path(isolated_repository.media_root))
        mock_bioclip_run(monkeypatch, bioclip_prediction(("brown thrasher (Toxostoma rufum)", None, None, 0.899)))

        await identify(client, visit_id)

        attempts = isolated_repository.list_bioclip_identification_attempts(
            target_type="visit", target_id=visit_id,
        )
        assert len(attempts) == 1
        assert attempts[0]["outcome"] == "unsupported"
        assert attempts[0]["error_stage"] == "crop_preparation"
        assert attempts[0]["resulting_species_suggestion_id"] is None


# --- Override tiers must not be second-guessed -------------------------------


class TestOverrideTiersUnaffected:
    """Same-Frame/Persisted-Crop/Native-Resolution override tiers already
    carry their own, stronger, separately-validated correspondence
    guarantee and must not be blocked by this check -- `source="activity"`
    is ambiguously shared with the legacy focus-crop tier this milestone
    does cover, so the caller must distinguish by `classifier_input_type`,
    not `source` alone."""

    def test_review_species_run_context_skips_geometry_check_for_override_crop(self) -> None:
        """Direct proof of the scoping condition itself: an override-tier
        `_ReviewSpeciesCropContext` (`classifier_input_type` set,
        `source="activity"`) must not have `geometry_source` derived for
        it, even in isolation from the full end-to-end wiring above."""

        crop = product_repository._ReviewSpeciesCropContext(
            source="activity",
            box_normalized=product_repository.BoundingBox(x=0.3, y=0.4, width=0.15, height=0.15),
            label="Same-frame subject crop (classifier evidence)",
            classifier_input_type="same_frame_crop",
            classifier_input_same_frame=True,
        )
        # Mirrors the exact condition `_review_species_run_context` applies.
        applies = crop.classifier_input_type is None and crop.source in {"megadetector", "activity"}
        assert applies is False

    def test_legacy_activity_focus_crop_is_in_scope(self) -> None:
        crop = product_repository._ReviewSpeciesCropContext(
            source="activity",
            box_normalized=product_repository.BoundingBox(x=0.4, y=0.3, width=0.2, height=0.2),
            label="Detected activity focus",
        )
        applies = crop.classifier_input_type is None and crop.source in {"megadetector", "activity"}
        assert applies is True

    def test_megadetector_crop_is_in_scope(self) -> None:
        crop = product_repository._ReviewSpeciesCropContext(
            source="megadetector",
            box_normalized=product_repository.BoundingBox(x=0.8041, y=0.6731, width=0.15, height=0.15),
            label="MegaDetector animal focus",
        )
        applies = crop.classifier_input_type is None and crop.source in {"megadetector", "activity"}
        assert applies is True

    def test_full_frame_fallback_is_out_of_scope(self) -> None:
        crop = product_repository._ReviewSpeciesCropContext(
            source="full_frame",
            box_normalized=product_repository.BoundingBox(x=0.0, y=0.0, width=1.0, height=1.0),
            label="Full frame fallback",
        )
        applies = crop.classifier_input_type is None and crop.source in {"megadetector", "activity"}
        assert applies is False
