"""Visit Same-Frame Classifier Evidence Visibility v1 (see docs/visit-
classifier-evidence-visibility-contract.md): a real field Visit
(visit-observation-candidate-022, 2026-08-16) proved the species classifier
can suggest a species from a `classifier_same_frame` MediaAsset the ordinary
Visit evidence gallery never shows -- while the Visit's own displayed
"identification" evidence happened to contain no visible bird. This file
proves `ProductRepository.classifier_supporting_evidence` makes that real
evidence reviewer-visible: exposed when it is genuinely distinct from
`evidence_frames`, suppressed when it would just duplicate an already-visible
asset, and degraded to `None` -- never raising -- whenever there is honestly
nothing to show.

Species suggestions are created directly via `create_species_suggestion`
with a hand-crafted `evidence_region` (mirroring the exact
`classifier_input` shape Same-Frame Species Evidence v1 persists) rather
than through a real BioCLIP call: this file tests the read/exposure seam in
isolation, decoupled from the resolver itself (already covered by
tests/test_same_frame_species_evidence.py).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from io import BytesIO
import json
from pathlib import Path

import asyncio
import httpx
import pytest
from PIL import Image

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import SpeciesSuggestionCreateRequest
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.contracts import CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE, GeometryAttribution
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    MediaAssetModel,
    ProductRepository,
    VisitEvidenceLinkModel,
)
from mockingbird.storage.models import CameraSourceModel, StreamModel
from tests.conftest import LegacyAuthenticatedSyncTestClient

SOURCE_ID = "source-classifier-evidence-test"
STREAM_ID = "stream-classifier-evidence-test"
OTHER_STREAM_ID = "stream-classifier-evidence-other"
NOW = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    # A fresh Source/Stream/second-Stream, independent of the seeded demo
    # graph, exactly like tests/test_same_frame_species_evidence.py -- no
    # Zone content that would otherwise interfere for unrelated reasons.
    with repo.session_factory() as session:
        with session.begin():
            session.add(CameraSourceModel(
                # "integration" (not the raw "camera_node" provider_key) and
                # "connected" (not "active") are what a real Camera Node
                # Source's `kind`/`status` actually store -- see
                # `_camera_setup_source_kind`/`SourceKind`/`SourceStatus`.
                # `ProductRepository.get_source` (exercised via Visit Detail's
                # `source_name` resolution, Camera / Source + Multi-Camera
                # Maturity v1) parses both strictly, so a fixture using the
                # provider key directly would fail there even though nothing
                # in this file exercised that path before.
                id=SOURCE_ID, name="Classifier Evidence Test Source", kind="integration",
                status="connected", description="Isolated fixture source.",
            ))
            session.add(StreamModel(
                id=STREAM_ID, source_id=SOURCE_ID, name="Classifier Evidence Test Stream",
                description="Isolated fixture stream.", is_live=True,
            ))
            session.add(StreamModel(
                id=OTHER_STREAM_ID, source_id=SOURCE_ID, name="Another Stream",
                description="A second Stream evidence must never leak from.", is_live=True,
            ))
    yield repo
    repo.close()


def _jpeg(*, width: int, height: int) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (width, height), color=(80, 120, 60)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _facts(proposal_id: str) -> CandidateVisitProposalFacts:
    return CandidateVisitProposalFacts(
        proposal_id=proposal_id,
        stream_id=STREAM_ID,
        zone_id=None,
        broad_class="animal",
        start_offset_ms=0,
        end_offset_ms=3500,
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
    proposal_id: str = "visit-episode:classifier-evidence-1",
) -> tuple[str, str, str | None]:
    """Real end-to-end persistence, mirroring tests/test_same_frame_species_
    evidence.py's own `_create_visit`. Returns `(visit_id,
    identification_media_asset_id, same_frame_media_asset_id_or_None)`."""

    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=NOW)
    items = [
        CandidateEvidenceItem(
            engine_media_id="shadow-burst:hash-1",
            role="identification",
            content=_jpeg(width=3840, height=2160),
            content_type="image/jpeg",
            width=3840,
            height=2160,
            captured_at=NOW,
            subject_geometry=(0.48, 0.57, 0.52, 0.63),
            geometry_attribution_json=json.dumps(asdict(GeometryAttribution(
                geometry_source="detector", geometry_source_offset_ms=500, geometry_source_observation_id="obs-1",
                geometry_source_confidence=0.9, same_frame=False, geometry_evidence_gap_ms=3358,
            ))),
        ),
    ]
    if include_same_frame:
        items.append(CandidateEvidenceItem(
            engine_media_id="shadow-same-frame:hash-1",
            role=CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
            content=_jpeg(width=1920, height=1440),
            content_type="image/jpeg",
            width=1920,
            height=1440,
            captured_at=NOW,
            subject_geometry=(0.48, 0.57, 0.52, 0.63),
            geometry_attribution_json=json.dumps(asdict(GeometryAttribution(
                geometry_source="detector", geometry_source_offset_ms=500, geometry_source_observation_id="obs-1",
                geometry_source_confidence=0.9, same_frame=True, geometry_evidence_gap_ms=0,
            ))),
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


def _suggest(
    repository: ProductRepository,
    *,
    visit_id: str,
    media_asset_id: str,
    evidence_region: dict | None,
    suggested_label: str = "house_finch",
) -> str:
    """A SpeciesSuggestion with a hand-crafted `evidence_region`, mirroring
    the exact `classifier_input` shape Same-Frame Species Evidence v1
    persists (see `_initial_bioclip_crop_provenance` in
    product_repository.py) -- without running real BioCLIP inference."""

    response = repository.create_species_suggestion(SpeciesSuggestionCreateRequest(
        source_id=SOURCE_ID, stream_id=STREAM_ID, visit_id=visit_id, media_asset_id=media_asset_id,
        adapter_id="bioclip_2", adapter_name="BioCLIP 2", suggested_label=suggested_label,
        confidence=0.99, rank=1, alternatives=[], evidence_region=evidence_region,
    ))
    return response.id


def _classifier_input_region(*, source_media_asset_id: str, same_frame: bool = True) -> dict:
    return {
        "source": "activity",
        "coordinate_space": "full_frame_normalized",
        "x": 0.43, "y": 0.53, "width": 0.15, "height": 0.15,
        "classifier_input": {
            "source_media_asset_id": source_media_asset_id,
            "input_type": "same_frame_crop" if same_frame else "persisted_crop",
            "same_frame": same_frame,
            "crop_method": "exact_frame_subject_box_padded",
            "source_width": 1920, "source_height": 1440,
            "classifier_input_width": 289, "classifier_input_height": 217,
        },
    }


# --- Core exposure: the real field scenario ---------------------------------


def test_distinct_same_frame_asset_is_returned(repository: ProductRepository) -> None:
    """The real 2026-08-16 field scenario: a classifier_same_frame asset,
    not the Visit's own identification evidence, supported the suggestion."""

    visit_id, identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    suggestion_id = _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=_classifier_input_region(source_media_asset_id=same_frame_id),
    )

    evidence = repository.classifier_supporting_evidence(visit_id)

    assert evidence is not None
    assert evidence.frame.media_asset_id == same_frame_id
    assert evidence.frame.media_asset_id != identification_id
    assert evidence.frame.evidence_role == CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE
    assert evidence.frame.is_primary is False
    assert evidence.frame.width == 1920 and evidence.frame.height == 1440
    assert evidence.same_frame is True
    assert evidence.input_type == "same_frame_crop"
    assert evidence.species_suggestion_id == suggestion_id


def test_supporting_evidence_frame_is_renderable_via_existing_media_serialization(
    repository: ProductRepository,
) -> None:
    """Reuses the exact `VisitEvidenceFrame` shape/preview URL convention
    the ordinary evidence gallery already uses -- proving the frontend's
    existing zoom/render mechanics apply with no new plumbing."""

    visit_id, identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=_classifier_input_region(source_media_asset_id=same_frame_id),
    )

    evidence = repository.classifier_supporting_evidence(visit_id)

    assert evidence is not None
    assert evidence.frame.preview_url == f"/api/media/{same_frame_id}/preview"
    assert evidence.frame.content_type == "image/jpeg"
    # Same-frame proof (a stronger, capture-time-proven fact than the
    # ordinary gallery's generic alignment check) authorizes the subject-box
    # overlay/"Focus on evidence" control here.
    assert evidence.frame.normalized_track_box == [0.48, 0.57, 0.52, 0.63]


def test_normalized_track_box_omitted_without_same_frame_proof(repository: ProductRepository) -> None:
    """Without a proven `same_frame=True` geometry attribution on the
    asset itself, no subject box is shown -- matches the ordinary
    gallery's own safe default rather than trusting an unproven box."""

    visit_id, identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    with repository.session_factory() as session:
        asset = session.get(MediaAssetModel, same_frame_id)
        assert asset is not None
        asset.geometry_attribution_json = json.dumps(asdict(GeometryAttribution(
            geometry_source="detector", geometry_source_offset_ms=500, geometry_source_observation_id="obs-1",
            geometry_source_confidence=0.9, same_frame=False, geometry_evidence_gap_ms=1200,
        )))
        session.commit()
    _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=_classifier_input_region(source_media_asset_id=same_frame_id, same_frame=False),
    )

    evidence = repository.classifier_supporting_evidence(visit_id)

    assert evidence is not None
    assert evidence.frame.normalized_track_box is None


# --- Duplicate suppression ---------------------------------------------------


def test_suppressed_when_asset_already_in_ordinary_evidence_frames(repository: ProductRepository) -> None:
    """Avoid duplicate-image clutter: when `classifier_input` points at an
    asset already visible in the ordinary gallery (the dormant
    `persisted_crop` tier's real-world shape -- an `activity_crop`/`user_
    refined_crop` asset is never excluded from `evidence_frames`), no
    redundant second copy is surfaced."""

    visit_id, identification_id, _same_frame_id = _create_visit(repository, include_same_frame=False)
    ordinary_frames = repository.visit_evidence_frames(visit_id)
    assert identification_id in {frame.media_asset_id for frame in ordinary_frames}
    _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=_classifier_input_region(
            source_media_asset_id=identification_id, same_frame=False,
        ),
    )

    evidence = repository.classifier_supporting_evidence(visit_id)

    assert evidence is None


def test_same_frame_asset_never_actually_visible_in_ordinary_gallery(repository: ProductRepository) -> None:
    """Sanity check on the premise the dedup logic relies on: a
    `classifier_same_frame` asset is structurally excluded from
    `evidence_frames` (Same-Frame Species Evidence v1), so the happy-path
    exposure test above is never accidentally suppressed by this check."""

    visit_id, _identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None

    ordinary_frames = repository.visit_evidence_frames(visit_id)

    assert same_frame_id not in {frame.media_asset_id for frame in ordinary_frames}


# --- Graceful degradation ----------------------------------------------------


def test_none_when_visit_has_no_species_suggestion(repository: ProductRepository) -> None:
    visit_id, _identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None

    assert repository.classifier_supporting_evidence(visit_id) is None


def test_none_when_suggestion_used_full_frame(repository: ProductRepository) -> None:
    """The common, honest case: the resolver found nothing better than the
    full frame, so the suggestion's own `evidence_region` carries no
    `classifier_input` key at all (see `_classifier_input_override`)."""

    visit_id, identification_id, _same_frame_id = _create_visit(repository, include_same_frame=False)
    _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region={"source": "full_frame", "coordinate_space": "full_frame_normalized",
                          "x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
    )

    assert repository.classifier_supporting_evidence(visit_id) is None


def test_none_when_evidence_region_is_null(repository: ProductRepository) -> None:
    visit_id, identification_id, _same_frame_id = _create_visit(repository, include_same_frame=False)
    _suggest(repository, visit_id=visit_id, media_asset_id=identification_id, evidence_region=None)

    assert repository.classifier_supporting_evidence(visit_id) is None


def test_none_when_referenced_asset_does_not_exist(repository: ProductRepository) -> None:
    visit_id, identification_id, _same_frame_id = _create_visit(repository, include_same_frame=False)
    _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=_classifier_input_region(source_media_asset_id="media-does-not-exist"),
    )

    assert repository.classifier_supporting_evidence(visit_id) is None


def test_degrades_cleanly_when_underlying_file_deleted(repository: ProductRepository) -> None:
    visit_id, identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    with repository.session_factory() as session:
        asset = session.get(MediaAssetModel, same_frame_id)
        assert asset is not None
        Path(asset.local_path).unlink()
    _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=_classifier_input_region(source_media_asset_id=same_frame_id),
    )

    assert repository.classifier_supporting_evidence(visit_id) is None


def test_malformed_evidence_region_does_not_raise(repository: ProductRepository) -> None:
    visit_id, identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    suggestion_id = _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=_classifier_input_region(source_media_asset_id=same_frame_id),
    )
    with repository.session_factory() as session:
        from mockingbird.repository.product_repository import SpeciesSuggestionModel
        suggestion = session.get(SpeciesSuggestionModel, suggestion_id)
        assert suggestion is not None
        suggestion.evidence_region_json = "{not-valid-json"
        session.commit()

    assert repository.classifier_supporting_evidence(visit_id) is None


# --- Cross-Visit/Stream leak prevention --------------------------------------


def test_rejects_asset_belonging_to_another_stream(repository: ProductRepository) -> None:
    """Evidence ownership stays Stream-scoped: a suggestion's stored
    `classifier_input` id is never trusted without re-verifying it still
    belongs to this Visit's own Stream, exactly like the ordinary evidence
    gallery's own anti-leak check."""

    visit_id, identification_id, _same_frame_id = _create_visit(repository, include_same_frame=False)
    with repository.session_factory() as session:
        with session.begin():
            other = MediaAssetModel(
                id="media-other-stream-asset", source_id=SOURCE_ID, stream_id=OTHER_STREAM_ID,
                filename="other.jpg", original_filename="other.jpg",
                content_type="image/jpeg", media_type="image",
                local_path=str(Path(repository.media_root) / "other.jpg"),
                file_size_bytes=len(_jpeg(width=1920, height=1440)),
                image_width=1920, image_height=1440, evidence_role=CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
                created_at=NOW,
            )
            session.add(other)
    Path(repository.media_root).mkdir(parents=True, exist_ok=True)
    Path(repository.media_root, "other.jpg").write_bytes(_jpeg(width=1920, height=1440))
    _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=_classifier_input_region(source_media_asset_id="media-other-stream-asset"),
    )

    assert repository.classifier_supporting_evidence(visit_id) is None


def test_does_not_leak_between_two_real_visits(repository: ProductRepository) -> None:
    """Two Visits, each with their own genuine classifier_same_frame
    evidence: each Visit's exposed evidence must be its own, never the
    other's."""

    visit_a, id_a, same_frame_a = _create_visit(repository, proposal_id="visit-episode:leak-a")
    visit_b, id_b, same_frame_b = _create_visit(repository, proposal_id="visit-episode:leak-b")
    assert same_frame_a is not None and same_frame_b is not None
    assert same_frame_a != same_frame_b
    _suggest(repository, visit_id=visit_a, media_asset_id=id_a,
             evidence_region=_classifier_input_region(source_media_asset_id=same_frame_a))
    _suggest(repository, visit_id=visit_b, media_asset_id=id_b,
             evidence_region=_classifier_input_region(source_media_asset_id=same_frame_b))

    evidence_a = repository.classifier_supporting_evidence(visit_a)
    evidence_b = repository.classifier_supporting_evidence(visit_b)

    assert evidence_a is not None and evidence_b is not None
    assert evidence_a.frame.media_asset_id == same_frame_a
    assert evidence_b.frame.media_asset_id == same_frame_b
    assert evidence_a.frame.media_asset_id != evidence_b.frame.media_asset_id


# --- Provenance / suggestion selection ---------------------------------------


def test_picks_latest_suggestion_when_more_than_one_exists(repository: ProductRepository) -> None:
    """Mirrors `mockingbird.api.main._latest_species_suggestion_for_visit`
    exactly: the evidence shown always explains the same suggestion a
    reviewer already sees as current."""

    visit_id, identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=None, suggested_label="unknown_bird",
    )
    newest_id = _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=_classifier_input_region(source_media_asset_id=same_frame_id),
        suggested_label="house_finch",
    )

    evidence = repository.classifier_supporting_evidence(visit_id)

    assert evidence is not None
    assert evidence.species_suggestion_id == newest_id


# --- Read-only / truth-preservation ------------------------------------------


def test_does_not_alter_suggestion_or_visit_review_state(repository: ProductRepository) -> None:
    """Preserve evidence truth: reading classifier-supporting evidence must
    never change the species suggestion's own values, the Visit's review
    status, or its reviewed label."""

    visit_id, identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    suggestion_id = _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=_classifier_input_region(source_media_asset_id=same_frame_id),
    )
    before_visit = repository.get_visit(visit_id)
    before_suggestions = repository.list_species_suggestions(visit_id=visit_id)
    assert before_visit is not None

    repository.classifier_supporting_evidence(visit_id)
    repository.classifier_supporting_evidence(visit_id)  # idempotent re-read

    after_visit = repository.get_visit(visit_id)
    after_suggestions = repository.list_species_suggestions(visit_id=visit_id)
    assert after_visit is not None
    assert after_visit.review_status == before_visit.review_status
    assert after_visit.reviewed_label == before_visit.reviewed_label
    assert after_visit.species_guess == before_visit.species_guess
    assert len(after_suggestions) == len(before_suggestions) == 1
    assert after_suggestions[0].id == suggestion_id
    assert after_suggestions[0].suggested_label == before_suggestions[0].suggested_label
    assert after_suggestions[0].confidence == before_suggestions[0].confidence
    assert after_suggestions[0].evidence_region == before_suggestions[0].evidence_region
    assert after_suggestions[0].status == before_suggestions[0].status


# --- End-to-end API wiring ----------------------------------------------------


def test_visit_detail_api_exposes_and_serves_classifier_supporting_evidence(
    repository: ProductRepository,
) -> None:
    """End-to-end: `GET /api/visits/{id}/detail` returns the new field with
    a real, fetchable preview image -- proving the frontend's existing
    evidence-viewer mechanics have real bytes to render/zoom, not just a
    plausible-looking repository object."""

    visit_id, identification_id, same_frame_id = _create_visit(repository)
    assert same_frame_id is not None
    _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region=_classifier_input_region(source_media_asset_id=same_frame_id),
    )
    configure_repository(repository)
    try:
        client = LegacyAuthenticatedSyncTestClient(app)
        detail_response = client.get(f"/api/visits/{visit_id}/detail")
        assert detail_response.status_code == 200
        body = detail_response.json()
        supporting = body["classifier_supporting_evidence"]
        assert supporting is not None
        assert supporting["frame"]["media_asset_id"] == same_frame_id
        assert supporting["same_frame"] is True
        # Never the Visit's primary/canonical evidence.
        assert supporting["frame"]["is_primary"] is False
        assert body["evidence_frames"][0]["media_asset_id"] != same_frame_id

        preview_response = client.get(supporting["frame"]["preview_url"])
        assert preview_response.status_code == 200
        assert preview_response.headers["content-type"].startswith("image/")
    finally:
        configure_repository(None)


def test_visit_detail_api_omits_field_cleanly_for_ordinary_visit(repository: ProductRepository) -> None:
    """A Visit with no classifier-supporting evidence gets a clean `null`,
    not a missing key or an error -- existing historical Visits degrade
    gracefully."""

    visit_id, identification_id, _same_frame_id = _create_visit(repository, include_same_frame=False)
    _suggest(
        repository, visit_id=visit_id, media_asset_id=identification_id,
        evidence_region={"source": "full_frame", "coordinate_space": "full_frame_normalized",
                          "x": 0.0, "y": 0.0, "width": 1.0, "height": 1.0},
    )
    configure_repository(repository)
    try:
        client = LegacyAuthenticatedSyncTestClient(app)
        detail_response = client.get(f"/api/visits/{visit_id}/detail")
        assert detail_response.status_code == 200
        body = detail_response.json()
        assert "classifier_supporting_evidence" in body
        assert body["classifier_supporting_evidence"] is None
    finally:
        configure_repository(None)
