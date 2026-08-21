"""Source-Resolution + Multi-Frame Species Evidence v1: the resolver-wiring
seam between a persisted, genuinely higher-resolution evidence MediaAsset
(`GeometryAttribution.resolution_provenance == "synchronized"`) and the
automatic BioCLIP species-assist path
(`ProductRepository.identify_review_queue_item`).

Mirrors `tests/test_same_frame_species_evidence.py`'s own established
pattern exactly (direct `CreateCandidateVisitRequest` construction, real
PIL-decodable solid-color JPEGs so the decode/crop path can be visually
proven, only the BioCLIP model call itself faked) -- see that file's module
docstring for the full rationale.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from io import BytesIO
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from mockingbird.api.schemas import ReviewIdentificationRequest
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.contracts import CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE, GeometryAttribution
from mockingbird.repository import product_repository
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    ProductRepository,
    VisitEvidenceLinkModel,
)
from mockingbird.storage.models import CameraSourceModel, StreamModel
from mockingbird.species.bioclip_adapter import (
    BIOCLIP_ADAPTER_ID,
    BioClipPrediction,
    BioClipProvenance,
    BioClipRankedSuggestion,
)

SOURCE_ID = "source-native-resolution-test"
STREAM_ID = "stream-native-resolution-test"
NOW = datetime(2026, 8, 21, 12, 0, 0, tzinfo=UTC)

# Real, distinguishable subject colors so a decode captured mid-test can
# prove *which* image the classifier input actually came from.
ANALYSIS_COLOR = (200, 30, 30)  # red: the low-resolution analysis-stream same-frame image
NATIVE_COLOR = (30, 160, 60)  # green: the genuinely higher-resolution, FOV-proven-aligned burst
FULL_FRAME_COLOR = (120, 120, 200)  # lavender: the ordinary review/primary asset


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    with repo.session_factory() as session:
        with session.begin():
            session.add(CameraSourceModel(
                id=SOURCE_ID, name="Native Resolution Test Source", kind="camera_node",
                status="active", description="Isolated fixture source; no Privacy/Ignore Zone attached.",
            ))
            session.add(StreamModel(
                id=STREAM_ID, source_id=SOURCE_ID, name="Native Resolution Test Stream",
                description="Isolated fixture stream.", is_live=True,
            ))
    yield repo
    repo.close()


def _solid_jpeg(*, width: int, height: int, color: tuple[int, int, int]) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=color).save(buffer, format="JPEG")
    return buffer.getvalue()


def _synchronized_attribution(
    *, source_offset_ms: int = 500, gap_ms: int = 340,
) -> str:
    return json.dumps(asdict(GeometryAttribution(
        geometry_source="detector", geometry_source_offset_ms=source_offset_ms,
        geometry_source_observation_id="obs-1", geometry_source_confidence=0.9,
        same_frame=False, geometry_evidence_gap_ms=gap_ms,
        fov_alignment_proven=True, geometry_transform_id="normalized-fov-test",
        resolution_provenance="synchronized",
    )))


def _same_frame_attribution() -> str:
    return json.dumps(asdict(GeometryAttribution(
        geometry_source="detector", geometry_source_offset_ms=500, geometry_source_observation_id="obs-1",
        geometry_source_confidence=0.9, same_frame=True, geometry_evidence_gap_ms=0,
    )))


def _facts(proposal_id: str) -> CandidateVisitProposalFacts:
    return CandidateVisitProposalFacts(
        proposal_id=proposal_id, stream_id=STREAM_ID, zone_id=None, broad_class="animal",
        start_offset_ms=0, end_offset_ms=4500, constituent_generation_ids=("gen-1",),
        constituent_track_ids=("track-1",), source_capture_frame_ids=("frame-1",),
        supporting_frame_ids=("frame-1",),
        evidence_candidate_ids=("shadow-full:hash-0", "shadow-burst:hash-1", "shadow-same-frame:hash-1"),
        limitation_facts=(), ambiguous_adjacent_proposal_ids=(),
        assembler_version="tracklet-visit-assembler-v1", detector_provenance="onnx-cuda",
        tracker_provenance="frame-driven-onnx-cuda-v1", provider_key="frame-driven-onnx-cuda",
    )


def _create_visit(
    repository: ProductRepository,
    *,
    include_native: bool = True,
    include_same_frame: bool = False,
    native_box: tuple[float, float, float, float] = (0.40, 0.55, 0.60, 0.75),
    native_geometry_attribution_json: str | None = "__default__",
    proposal_id: str = "visit-episode:native-resolution-1",
) -> tuple[str, str, str | None, str | None]:
    """Returns `(visit_id, primary_media_asset_id, native_media_asset_id_or_None,
    same_frame_media_asset_id_or_None)`."""

    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    items = [
        # The Visit's own "identification" pick -- its ordinary primary/
        # review asset -- is deliberately a *different* (lower-quality,
        # analysis-resolution-like) image than the native-resolution
        # candidate below, mirroring test_same_frame_species_evidence.py's
        # own separation of "primary FK" from "classifier-input override
        # target": proves the override reaches past the Visit's canonical
        # image rather than merely agreeing with it by construction.
        CandidateEvidenceItem(
            engine_media_id="shadow-full:hash-0",
            role="identification",
            content=_solid_jpeg(width=1920, height=1080, color=FULL_FRAME_COLOR),
            content_type="image/jpeg", width=1920, height=1080, captured_at=NOW,
            subject_geometry=(0.3, 0.3, 0.7, 0.7), geometry_attribution_json=None,
        ),
    ]
    if include_native:
        if native_geometry_attribution_json == "__default__":
            native_geometry_attribution_json = _synchronized_attribution()
        items.append(CandidateEvidenceItem(
            engine_media_id="shadow-burst:hash-1",
            role="alternate",
            content=_solid_jpeg(width=4624, height=3472, color=NATIVE_COLOR),
            content_type="image/jpeg", width=4624, height=3472, captured_at=NOW,
            subject_geometry=native_box, geometry_attribution_json=native_geometry_attribution_json,
        ))
    if include_same_frame:
        items.append(CandidateEvidenceItem(
            engine_media_id="shadow-same-frame:hash-1",
            role=CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
            content=_solid_jpeg(width=640, height=480, color=ANALYSIS_COLOR),
            content_type="image/jpeg", width=640, height=480, captured_at=NOW,
            subject_geometry=(0.4, 0.4, 0.5, 0.5), geometry_attribution_json=_same_frame_attribution(),
        ))
    outcome = repository.create_candidate_visit_from_proposal(CreateCandidateVisitRequest(
        proposal=_facts(proposal_id), observed_at=NOW, evidence_items=tuple(items),
    ))
    assert outcome.outcome == "created", outcome.reason
    assert outcome.visit_id is not None
    with repository.session_factory() as session:
        links = session.query(VisitEvidenceLinkModel).filter_by(visit_id=outcome.visit_id).all()
        primary_id = next(link.media_asset_id for link in links if link.evidence_role == "identification")
        native_link = next(
            (link for link in links if link.evidence_role == "alternate"), None,
        )
        same_frame_link = next(
            (link for link in links if link.evidence_role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE), None,
        )
    return (
        outcome.visit_id, primary_id,
        native_link.media_asset_id if native_link is not None else None,
        same_frame_link.media_asset_id if same_frame_link is not None else None,
    )


def _mark_bioclip_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        product_repository,
        "get_bioclip_status",
        lambda _config: SimpleNamespace(
            status="available", configured=True, runtime_available=True,
            detail="Mock BioCLIP available for native-resolution evidence tests.",
            model_dir=str(tmp_path / "model"), labels_path=str(tmp_path / "labels.txt"),
            embedding_cache_path=str(tmp_path / "cache.npz"), device="cpu", labels_sha256="a" * 64,
        ),
    )


def _prediction() -> BioClipPrediction:
    labels = ("house finch (Haemorhous mexicanus)", "red-bellied woodpecker (Melanerpes carolinus)")
    import hashlib as _hashlib
    return BioClipPrediction(
        suggestions=(
            BioClipRankedSuggestion(rank=1, label=labels[0], common_name=None, scientific_name=None, score=0.93),
            BioClipRankedSuggestion(rank=2, label=labels[1], common_name=None, scientific_name=None, score=0.04),
        ),
        provenance=BioClipProvenance(
            adapter_id=BIOCLIP_ADAPTER_ID, adapter_name="BioCLIP 2 (local)", model_name="BioCLIP 2 local test",
            device="cpu", open_clip_version="3.3.0", torch_version="2.13.0+cpu", label_count=len(labels),
            labels_sha256=_hashlib.sha256("\n".join(labels).encode("utf-8")).hexdigest(),
            embedding_cache_sha256="b" * 64, model_config_sha256="c" * 64,
            model_weights_name="open_clip_model.safetensors", model_weights_sha256="d" * 64,
            prompt_recipe_id="backyard-core-v1", prompt_recipe_sha256="e" * 64,
            score_kind="candidate_relative_similarity", calibrated=False,
        ),
        candidate_labels=labels, candidate_scores=(0.93, 0.04),
    )


def _run_bioclip_for_real_pixels(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    captured: dict[str, object] = {}

    def run_image(image_loader, _config, top_k: int = 5, *, on_prepared=None):
        image = image_loader()
        captured["image"] = image
        captured["size"] = image.size
        captured["mean_color"] = tuple(round(value) for value in _average_color(image))
        return _prediction()

    monkeypatch.setattr(product_repository, "run_bioclip_from_image_loader", run_image)
    return captured


def _average_color(image) -> tuple[float, float, float]:
    small = image.resize((1, 1))
    pixel = small.getpixel((0, 0))
    return float(pixel[0]), float(pixel[1]), float(pixel[2])


def _closest(color: tuple[float, float, float], candidates: dict[str, tuple[int, int, int]]) -> str:
    return min(
        candidates,
        key=lambda name: sum((color[i] - candidates[name][i]) ** 2 for i in range(3)),
    )


def test_resolver_prefers_native_resolution_crop_when_no_same_frame_asset(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    visit_id, primary_id, native_id, _ = _create_visit(repository)
    assert native_id is not None
    _mark_bioclip_available(monkeypatch, tmp_path)
    _run_bioclip_for_real_pixels(monkeypatch)

    response = repository.identify_review_queue_item(
        "visit", visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    assert response.identification.status.value == "suggestion_created"
    suggestion = response.species_suggestion
    assert suggestion is not None
    classifier_input = suggestion.evidence_region["classifier_input"]
    assert classifier_input["input_type"] == "native_resolution_crop"
    assert classifier_input["same_frame"] is False
    assert classifier_input["source_media_asset_id"] == native_id
    assert classifier_input["source_width"] == 4624
    assert classifier_input["source_height"] == 3472
    # The persisted MediaAsset FK stays the Visit's own primary/review frame
    # throughout -- never silently repointed at the diagnostic native asset.
    assert suggestion.media_asset_id == primary_id


def test_real_decoded_pixels_come_from_the_native_asset_not_the_primary_frame(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Direct visual proof: the real, unpatched decode path reads pixels
    from the native-resolution (green) image, never the ordinary primary
    (lavender) frame, when the resolver picks the native tier."""

    visit_id, _primary_id, native_id, _ = _create_visit(repository)
    assert native_id is not None
    _mark_bioclip_available(monkeypatch, tmp_path)
    captured = _run_bioclip_for_real_pixels(monkeypatch)

    response = repository.identify_review_queue_item(
        "visit", visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    assert response.identification.status.value == "suggestion_created"
    assert _closest(
        captured["mean_color"], {"native": NATIVE_COLOR, "full_frame": FULL_FRAME_COLOR},
    ) == "native"


def test_native_resolution_crop_is_preferred_over_same_resolution_same_frame_crop(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Resolution first, given honest correspondence: when both a proven
    same-frame asset and a proven native-resolution asset exist for one
    Visit, the genuinely higher-resolution evidence wins."""

    visit_id, _primary_id, native_id, same_frame_id = _create_visit(
        repository, include_same_frame=True,
    )
    assert native_id is not None and same_frame_id is not None
    _mark_bioclip_available(monkeypatch, tmp_path)
    captured = _run_bioclip_for_real_pixels(monkeypatch)

    response = repository.identify_review_queue_item(
        "visit", visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    assert response.identification.status.value == "suggestion_created"
    classifier_input = response.species_suggestion.evidence_region["classifier_input"]
    assert classifier_input["input_type"] == "native_resolution_crop"
    assert classifier_input["source_media_asset_id"] == native_id
    assert _closest(
        captured["mean_color"], {"native": NATIVE_COLOR, "analysis": ANALYSIS_COLOR},
    ) == "native"


@pytest.mark.parametrize(
    "resolution_provenance,fov_alignment_proven",
    [("near_time_capture", None), ("near_time_capture", False), ("fallback", None), (None, None)],
)
def test_unproven_burst_never_becomes_a_native_resolution_crop(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
    resolution_provenance: str | None, fov_alignment_proven: bool | None,
) -> None:
    """The same 'proof, not proximity' discipline enforced at the pure
    resolver level (see tests/test_classifier_input.py) holds end-to-end
    through real persistence: a burst without a *proven* synchronized
    correspondence never becomes automatic, unreviewed classifier input."""

    attribution = json.dumps(asdict(GeometryAttribution(
        geometry_source="detector", geometry_source_offset_ms=500, geometry_source_observation_id="obs-1",
        geometry_source_confidence=0.9, same_frame=False, geometry_evidence_gap_ms=340,
        fov_alignment_proven=fov_alignment_proven, resolution_provenance=resolution_provenance,
    )))
    visit_id, primary_id, native_id, _ = _create_visit(
        repository, native_geometry_attribution_json=attribution,
    )
    assert native_id is not None
    _mark_bioclip_available(monkeypatch, tmp_path)
    _run_bioclip_for_real_pixels(monkeypatch)

    response = repository.identify_review_queue_item(
        "visit", visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    assert response.identification.status.value == "suggestion_created"
    # No "classifier_input" key at all is the honest outcome of falling all
    # the way through to megadetector/activity/full_frame (that key is only
    # ever written by the same-frame/native override tiers); either that, or
    # a present key that is explicitly not the native tier, both prove the
    # unproven burst was correctly rejected.
    classifier_input = response.species_suggestion.evidence_region.get("classifier_input") or {}
    assert classifier_input.get("input_type") != "native_resolution_crop"


def test_missing_native_asset_falls_back_honestly(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    visit_id, primary_id, native_id, _ = _create_visit(repository, include_native=False)
    assert native_id is None
    _mark_bioclip_available(monkeypatch, tmp_path)
    _run_bioclip_for_real_pixels(monkeypatch)

    response = repository.identify_review_queue_item(
        "visit", visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    assert response.identification.status.value == "suggestion_created"
    classifier_input = response.species_suggestion.evidence_region.get("classifier_input") or {}
    assert classifier_input.get("input_type") != "native_resolution_crop"


def test_sibling_visit_never_borrows_another_visits_native_resolution_evidence(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Multi-subject correctness (Section 17): each Visit's own native-
    resolution evidence must stay subject-specific -- no sibling evidence
    borrowing, even for two Visits on the same Stream."""

    first_visit_id, _first_primary, first_native_id, _ = _create_visit(
        repository, proposal_id="visit-episode:native-resolution-a",
        native_box=(0.10, 0.10, 0.20, 0.20),
    )
    second_visit_id, second_primary_id, second_native_id, _ = _create_visit(
        repository, include_native=False, proposal_id="visit-episode:native-resolution-b",
    )
    assert first_native_id is not None
    assert second_native_id is None
    assert first_visit_id != second_visit_id

    _mark_bioclip_available(monkeypatch, tmp_path)
    _run_bioclip_for_real_pixels(monkeypatch)
    response = repository.identify_review_queue_item(
        "visit", second_visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    assert response.identification.status.value == "suggestion_created"
    classifier_input = response.species_suggestion.evidence_region.get("classifier_input") or {}
    assert classifier_input.get("input_type") != "native_resolution_crop"
    assert classifier_input.get("source_media_asset_id") != first_native_id


# ---------------------------------------------------------------------------
# species_multi_frame_candidate_plans: the bounded, read-only, non-mutating
# multi-frame candidate-selection primitive (Phase D).
# ---------------------------------------------------------------------------


def test_multi_frame_candidate_plans_includes_same_frame_and_native_tiers(
    repository: ProductRepository,
) -> None:
    visit_id, _primary_id, native_id, same_frame_id = _create_visit(
        repository, include_same_frame=True,
    )
    assert native_id is not None and same_frame_id is not None

    plans = repository.species_multi_frame_candidate_plans(visit_id)
    assert [plan.media_asset_id for plan in plans] == [same_frame_id, native_id]
    assert [plan.source for plan in plans] == ["exact_frame_subject_box", "native_resolution_subject_box"]


def test_multi_frame_candidate_plans_never_runs_a_model_or_mutates_the_visit(
    repository: ProductRepository,
) -> None:
    visit_id, _primary_id, native_id, _ = _create_visit(repository)
    assert native_id is not None
    before = repository.get_visit(visit_id)
    plans = repository.species_multi_frame_candidate_plans(visit_id)
    after = repository.get_visit(visit_id)
    assert len(plans) == 1
    assert before.review_status == after.review_status
    assert before.species_guess == after.species_guess


def test_multi_frame_candidate_plans_is_bounded(
    repository: ProductRepository,
) -> None:
    visit_id, _primary_id, native_id, same_frame_id = _create_visit(
        repository, include_same_frame=True,
    )
    assert native_id is not None and same_frame_id is not None
    plans = repository.species_multi_frame_candidate_plans(visit_id, max_candidates=1)
    assert len(plans) == 1
    assert plans[0].media_asset_id == same_frame_id


def test_multi_frame_candidate_plans_empty_when_nothing_eligible(
    repository: ProductRepository,
) -> None:
    visit_id, _primary_id, native_id, _ = _create_visit(repository, include_native=False)
    assert native_id is None
    assert repository.species_multi_frame_candidate_plans(visit_id) == ()


def test_multi_frame_candidate_plans_rejects_non_positive_bound(
    repository: ProductRepository,
) -> None:
    visit_id, _primary_id, _native_id, _ = _create_visit(repository)
    with pytest.raises(ValueError):
        repository.species_multi_frame_candidate_plans(visit_id, max_candidates=0)


def test_multi_frame_candidate_plans_deterministic_across_repeated_calls(
    repository: ProductRepository,
) -> None:
    visit_id, _primary_id, native_id, same_frame_id = _create_visit(
        repository, include_same_frame=True,
    )
    assert native_id is not None and same_frame_id is not None
    first = repository.species_multi_frame_candidate_plans(visit_id)
    second = repository.species_multi_frame_candidate_plans(visit_id)
    assert first == second
