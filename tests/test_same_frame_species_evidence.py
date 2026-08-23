"""Same-Frame Species Evidence v1 (see docs/same-frame-species-evidence-
contract.md): the resolver-wiring seam between a persisted
`classifier_same_frame` MediaAsset and the automatic BioCLIP species-assist
path (`ProductRepository.identify_review_queue_item`).

Uses the same direct `CreateCandidateVisitRequest` construction
`tests/test_candidate_visit_repository.py` already establishes (bypassing the
assembler/adapter, which `tests/test_candidate_visit_adapter.py` and
`tests/test_observation_camera_node_live.py` already cover) so each test can
control exact image bytes/dimensions/geometry without a real tracker.
`_load_bioclip_input_image` is deliberately left unpatched in most tests here
(only the model call itself, `run_bioclip_from_image_loader`, is faked) so
the real PIL decode/crop path -- unmodified by this milestone -- proves the
persisted pixels and the resolver's crop box actually agree.
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
    MediaAssetModel,
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

SOURCE_ID = "source-same-frame-test"
STREAM_ID = "stream-same-frame-test"
NOW = datetime(2026, 8, 14, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    # A fresh Source/Stream deliberately independent of the seeded demo
    # graph -- the demo stream carries its own legitimate Privacy/Ignore
    # Zone content, which would otherwise suppress every full-frame
    # fallback this file's tests exercise for a completely unrelated reason
    # (`_review_species_crop_intersects_restricted_zone` conservatively
    # treats *any* full-frame crop as intersecting *any* active restricted
    # zone on the Stream, existing behavior this milestone leaves
    # untouched). No zone at all is attached to this Stream.
    with repo.session_factory() as session:
        with session.begin():
            session.add(CameraSourceModel(
                # "integration"/"connected" (not the raw "camera_node"
                # provider_key / "active") match what a real Camera Node
                # Source's `kind`/`status` actually store -- see
                # `_camera_setup_source_kind`/`SourceKind`/`SourceStatus`.
                id=SOURCE_ID, name="Same-Frame Test Source", kind="integration",
                status="connected", description="Isolated fixture source for same-frame evidence tests.",
            ))
            session.add(StreamModel(
                id=STREAM_ID, source_id=SOURCE_ID, name="Same-Frame Test Stream",
                description="Isolated fixture stream.", is_live=True,
            ))
    yield repo
    repo.close()


def _solid_jpeg(*, width: int, height: int, color: tuple[int, int, int]) -> bytes:
    """A real, PIL-decodable JPEG -- unlike the other repository tests' fake
    `b"\\xff\\xd8..."` byte strings, this milestone's tests need `_load_
    bioclip_input_image` (left unpatched) to actually decode and crop real
    pixels, so the solid fill color can prove *which* image was read."""

    buffer = BytesIO()
    Image.new("RGB", (width, height), color=color).save(buffer, format="JPEG")
    return buffer.getvalue()


SAME_FRAME_COLOR = (200, 30, 30)  # red: the exact analysis-stream frame
BURST_COLOR = (30, 60, 200)  # blue: the later, separate high-resolution burst


def _facts(proposal_id: str = "visit-episode:same-frame-1") -> CandidateVisitProposalFacts:
    return CandidateVisitProposalFacts(
        proposal_id=proposal_id,
        stream_id=STREAM_ID,
        zone_id=None,
        broad_class="animal",
        start_offset_ms=0,
        end_offset_ms=4500,
        constituent_generation_ids=("gen-1",),
        constituent_track_ids=("track-1",),
        source_capture_frame_ids=("frame-1",),
        supporting_frame_ids=("frame-1",),
        evidence_candidate_ids=("shadow-burst:hash-1", "shadow-same-frame:hash-1"),
        limitation_facts=(),
        ambiguous_adjacent_proposal_ids=(),
        assembler_version="tracklet-visit-assembler-v1",
        detector_provenance="onnx-cuda",
        tracker_provenance="frame-driven-onnx-cuda-v1",
        provider_key="frame-driven-onnx-cuda",
    )


def _create_visit(
    repository: ProductRepository,
    *,
    include_same_frame: bool = True,
    same_frame_box: tuple[float, float, float, float] = (0.4, 0.4, 0.5, 0.5),
    same_frame_geometry_attribution_json: str | None = "__default__",
    proposal_id: str = "visit-episode:same-frame-1",
) -> tuple[str, str, str | None]:
    """Real end-to-end persistence through `create_candidate_visit_from_
    proposal` -- returns `(visit_id, identification_media_asset_id,
    same_frame_media_asset_id_or_None)`."""

    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    items = [
        CandidateEvidenceItem(
            engine_media_id="shadow-burst:hash-1",
            role="identification",
            content=_solid_jpeg(width=1920, height=1080, color=BURST_COLOR),
            content_type="image/jpeg",
            width=1920,
            height=1080,
            captured_at=NOW,
            subject_geometry=(0.4, 0.4, 0.5, 0.5),
            geometry_attribution_json=json.dumps(asdict(GeometryAttribution(
                geometry_source="detector", geometry_source_offset_ms=500, geometry_source_observation_id="obs-1",
                geometry_source_confidence=0.9, same_frame=False, geometry_evidence_gap_ms=4200,
            ))),
        ),
    ]
    if include_same_frame:
        if same_frame_geometry_attribution_json == "__default__":
            same_frame_geometry_attribution_json = json.dumps(asdict(GeometryAttribution(
                geometry_source="detector", geometry_source_offset_ms=500, geometry_source_observation_id="obs-1",
                geometry_source_confidence=0.9, same_frame=True, geometry_evidence_gap_ms=0,
            )))
        items.append(CandidateEvidenceItem(
            engine_media_id="shadow-same-frame:hash-1",
            role=CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
            content=_solid_jpeg(width=640, height=480, color=SAME_FRAME_COLOR),
            content_type="image/jpeg",
            width=640,
            height=480,
            captured_at=NOW,
            subject_geometry=same_frame_box,
            geometry_attribution_json=same_frame_geometry_attribution_json,
        ))
    outcome = repository.create_candidate_visit_from_proposal(CreateCandidateVisitRequest(
        proposal=_facts(proposal_id), observed_at=NOW, evidence_items=tuple(items),
    ))
    assert outcome.outcome == "created", outcome.reason
    assert outcome.visit_id is not None
    with repository.session_factory() as session:
        links = session.query(VisitEvidenceLinkModel).filter_by(visit_id=outcome.visit_id).all()
        identification_id = next(
            link.media_asset_id for link in links if link.evidence_role == "identification"
        )
        same_frame_link = next(
            (link for link in links if link.evidence_role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE), None,
        )
        same_frame_id = same_frame_link.media_asset_id if same_frame_link is not None else None
    return outcome.visit_id, identification_id, same_frame_id


def _mark_bioclip_available(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        product_repository,
        "get_bioclip_status",
        lambda _config: SimpleNamespace(
            status="available", configured=True, runtime_available=True,
            detail="Mock BioCLIP available for same-frame evidence tests.",
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
    """Leaves `_load_bioclip_input_image` UNPATCHED -- the real decode/crop
    path this milestone wires runs for real. Only the model call itself is
    faked, capturing the decoded (and, when eligible, cropped) image it
    actually received."""

    captured: dict[str, object] = {}

    def run_image(image_loader, _config, top_k: int = 5, *, on_prepared=None):
        image = image_loader()
        captured["image"] = image
        captured["size"] = image.size
        captured["mean_color"] = tuple(
            round(value) for value in _average_color(image)
        )
        return _prediction()

    monkeypatch.setattr(product_repository, "run_bioclip_from_image_loader", run_image)
    return captured


def _average_color(image) -> tuple[float, float, float]:
    small = image.resize((1, 1))
    pixel = small.getpixel((0, 0))
    return float(pixel[0]), float(pixel[1]), float(pixel[2])


def _closer_to(color: tuple[float, float, float], a: tuple[int, int, int], b: tuple[int, int, int]) -> str:
    distance_a = sum((color[index] - a[index]) ** 2 for index in range(3))
    distance_b = sum((color[index] - b[index]) ** 2 for index in range(3))
    return "a" if distance_a < distance_b else "b"


def test_resolver_prefers_same_frame_crop_over_full_frame(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    visit_id, identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    _mark_bioclip_available(monkeypatch, tmp_path)
    _run_bioclip_for_real_pixels(monkeypatch)

    response = repository.identify_review_queue_item(
        "visit", visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    assert response.identification.status.value == "suggestion_created"
    suggestion = response.species_suggestion
    assert suggestion is not None
    region = suggestion.evidence_region
    assert region is not None
    classifier_input = region["classifier_input"]
    assert classifier_input["input_type"] == "same_frame_crop"
    assert classifier_input["same_frame"] is True
    assert classifier_input["source_media_asset_id"] == same_frame_id
    assert classifier_input["source_width"] == 640
    assert classifier_input["source_height"] == 480
    # The persisted MediaAsset FK stays the Visit's own review/primary frame
    # (the burst) throughout -- never silently repointed at the diagnostic
    # same-frame asset (see "Do not promote... to canonical Visit image").
    assert suggestion.media_asset_id == identification_id


def test_derived_crop_pixels_come_from_same_frame_asset_not_burst(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Direct visual proof at the unit level: the real, unpatched decode
    path reads pixels from the same-frame (red) image, never the burst
    (blue) image, when the resolver picks the same-frame tier."""

    visit_id, _identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    _mark_bioclip_available(monkeypatch, tmp_path)
    captured = _run_bioclip_for_real_pixels(monkeypatch)

    response = repository.identify_review_queue_item(
        "visit", visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    assert response.identification.status.value == "suggestion_created"
    assert "mean_color" in captured
    assert _closer_to(captured["mean_color"], SAME_FRAME_COLOR, BURST_COLOR) == "a"


def test_padding_expands_beyond_raw_box_and_clamps_to_image_bounds(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    # A box hard against the image edge, to prove clamping as well as padding.
    raw_box = (0.02, 0.02, 0.12, 0.12)
    visit_id, _identification_id, same_frame_id = _create_visit(repository, same_frame_box=raw_box)
    assert same_frame_id is not None
    _mark_bioclip_available(monkeypatch, tmp_path)
    _run_bioclip_for_real_pixels(monkeypatch)

    response = repository.identify_review_queue_item(
        "visit", visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    suggestion = response.species_suggestion
    assert suggestion is not None
    region = suggestion.evidence_region
    box = (region["x"], region["y"], region["x"] + region["width"], region["y"] + region["height"])
    # Generous context, not a tight crop to the raw box.
    assert box[2] - box[0] > raw_box[2] - raw_box[0]
    assert box[3] - box[1] > raw_box[3] - raw_box[1]
    # Clamped to the image; a box touching (0.02, 0.02) padded outward must
    # not go negative.
    assert box[0] >= 0.0 and box[1] >= 0.0
    assert box[2] <= 1.0 and box[3] <= 1.0
    assert box[0] == pytest.approx(0.0, abs=1e-9)
    assert box[1] == pytest.approx(0.0, abs=1e-9)


def test_missing_same_frame_asset_falls_back_to_full_frame_honestly(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    visit_id, identification_id, same_frame_id = _create_visit(repository, include_same_frame=False)
    assert same_frame_id is None
    _mark_bioclip_available(monkeypatch, tmp_path)
    captured = _run_bioclip_for_real_pixels(monkeypatch)

    response = repository.identify_review_queue_item(
        "visit", visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    assert response.identification.status.value == "suggestion_created"
    suggestion = response.species_suggestion
    assert suggestion is not None
    region = suggestion.evidence_region
    assert region is not None
    assert region["source"] == "full_frame"
    assert "classifier_input" not in region
    # Full-frame fallback reads the burst's own (blue) pixels -- the only
    # image that exists for this Visit.
    assert _closer_to(captured["mean_color"], SAME_FRAME_COLOR, BURST_COLOR) == "b"


def test_deleted_same_frame_file_degrades_safely_without_blocking_inference(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """Missing/deleted classifier asset degrades safely: the MediaAsset row
    (and its VisitEvidenceLink) still exist, but the underlying file is
    gone -- species inference must still complete honestly on the full
    frame, never fail or block the Visit's identification."""

    visit_id, _identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    with repository.session_factory() as session:
        asset = session.get(MediaAssetModel, same_frame_id)
        assert asset is not None
        Path(asset.local_path).unlink()
    _mark_bioclip_available(monkeypatch, tmp_path)
    captured = _run_bioclip_for_real_pixels(monkeypatch)

    response = repository.identify_review_queue_item(
        "visit", visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    assert response.identification.status.value == "suggestion_created"
    suggestion = response.species_suggestion
    assert suggestion is not None
    assert suggestion.evidence_region["source"] == "full_frame"
    assert _closer_to(captured["mean_color"], SAME_FRAME_COLOR, BURST_COLOR) == "b"


def test_malformed_geometry_attribution_falls_back_without_raising(
    repository: ProductRepository, monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """A corrupt `geometry_attribution_json` on the same-frame asset (never
    expected in practice, but never trusted blindly either) must not crash
    species inference -- `_classifier_input_override` catches it and falls
    back exactly like a missing asset would."""

    visit_id, _identification_id, same_frame_id = _create_visit(
        repository, same_frame_geometry_attribution_json="{not-valid-json",
    )
    assert same_frame_id is not None
    _mark_bioclip_available(monkeypatch, tmp_path)
    _run_bioclip_for_real_pixels(monkeypatch)

    response = repository.identify_review_queue_item(
        "visit", visit_id, ReviewIdentificationRequest(adapter_id=BIOCLIP_ADAPTER_ID),
    )
    assert response.identification.status.value == "suggestion_created"
    assert response.species_suggestion.evidence_region["source"] == "full_frame"


def test_same_frame_evidence_never_appears_in_human_facing_evidence_gallery(
    repository: ProductRepository,
) -> None:
    """Do not promote the classifier crop to the canonical/browsable Visit
    evidence gallery: it is supporting classifier/diagnostic evidence only."""

    visit_id, identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    frames = repository.visit_evidence_frames(visit_id)
    assert identification_id in {frame.media_asset_id for frame in frames}
    assert same_frame_id not in {frame.media_asset_id for frame in frames}
    preview = repository.effective_primary_preview(visit_id)
    assert preview is not None
    assert preview["selected_media_asset_id"] != same_frame_id


def test_same_frame_evidence_no_duplicate_on_idempotent_replay(repository: ProductRepository) -> None:
    """A retried/replayed call for the same proposal_id converges on exactly
    one Visit and exactly one persisted `classifier_same_frame` MediaAsset --
    `create_candidate_visit_from_proposal`'s own generic idempotency
    boundary, unmodified by this milestone, already guarantees this; this
    test proves it holds for the new evidence item specifically."""

    visit_id, _identification_id, same_frame_id = _create_visit(repository, proposal_id="visit-episode:replay-1")
    assert same_frame_id is not None

    replayed_items = (
        CandidateEvidenceItem(
            engine_media_id="shadow-burst:hash-1", role="identification",
            content=_solid_jpeg(width=1920, height=1080, color=BURST_COLOR), content_type="image/jpeg",
            width=1920, height=1080, captured_at=NOW, subject_geometry=(0.4, 0.4, 0.5, 0.5),
        ),
        CandidateEvidenceItem(
            engine_media_id="shadow-same-frame:hash-1", role=CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
            content=_solid_jpeg(width=640, height=480, color=SAME_FRAME_COLOR), content_type="image/jpeg",
            width=640, height=480, captured_at=NOW, subject_geometry=(0.4, 0.4, 0.5, 0.5),
        ),
    )
    replay_outcome = repository.create_candidate_visit_from_proposal(CreateCandidateVisitRequest(
        proposal=_facts("visit-episode:replay-1"), observed_at=NOW, evidence_items=replayed_items,
    ))
    assert replay_outcome.outcome == "idempotent_repeat"
    assert replay_outcome.visit_id == visit_id

    with repository.session_factory() as session:
        same_frame_links = session.query(VisitEvidenceLinkModel).filter_by(
            visit_id=visit_id, evidence_role=CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
        ).all()
        assert len(same_frame_links) == 1
        assert same_frame_links[0].media_asset_id == same_frame_id
        same_frame_asset_count = session.query(MediaAssetModel).filter_by(
            evidence_role=CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
        ).count()
        assert same_frame_asset_count == 1
