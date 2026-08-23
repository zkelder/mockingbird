"""Multimodal Observation & Soundscape v1, Phase K: repository-integration
tests for `ProductRepository.soundscape_summary`. Isolated `tmp_path`
SQLite database, real candidate-Visit admission -- mirrors
`tests/test_multimodal_observation_acceptance.py`'s own conventions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.repository.product_repository import (
    AcousticDetectionFacts,
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    MediaAssetModel,
    ProductRepository,
)

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
NOW = datetime(2026, 8, 22, 9, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _activate(repository: ProductRepository, *, now: datetime = NOW) -> None:
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=now)


def _create_visual_visit(repository: ProductRepository, *, proposal_id: str, observed_at: datetime) -> str:
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=CandidateVisitProposalFacts(
                proposal_id=proposal_id, stream_id=STREAM_ID, zone_id=FEEDER_ZONE_ID, broad_class="bird",
                start_offset_ms=0, end_offset_ms=2000, constituent_generation_ids=("gen-1",),
                constituent_track_ids=("track-1",), source_capture_frame_ids=("frame-1",),
                supporting_frame_ids=("frame-1",), evidence_candidate_ids=(f"shadow-burst:{proposal_id}",),
                limitation_facts=(), ambiguous_adjacent_proposal_ids=(), concurrent_sibling_proposal_ids=(),
                assembler_version="tracklet-visit-assembler-v1", detector_provenance="onnx-cuda",
                tracker_provenance="frame-driven-onnx-cuda-v1", provider_key="frame-driven-onnx-cuda",
                confidence_evidence_json=None,
            ),
            observed_at=observed_at,
            evidence_items=(
                CandidateEvidenceItem(
                    engine_media_id=f"shadow-burst:{proposal_id}", role="identification", content=JPEG_BYTES,
                    content_type="image/jpeg", width=1920, height=1080, captured_at=observed_at,
                    subject_geometry=(0.4, 0.4, 0.6, 0.6), geometry_attribution_json=None,
                ),
            ),
        )
    )
    assert outcome.outcome == "created"
    return outcome.visit_id


def _seed_audio_and_create_acoustic_visit(
    repository: ProductRepository, *, media_asset_id: str, common_name: str, scientific_name: str, observed_at: datetime,
) -> str:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_asset_id, source_id="source-backyard-demo", stream_id=STREAM_ID,
                    filename=f"{media_asset_id}.wav", content_type="audio/wav", media_type="audio",
                    local_path=f"/tmp/{media_asset_id}.wav", original_filename=f"{media_asset_id}.wav",
                    file_size_bytes=1024, created_at=datetime.now(UTC), captured_at=observed_at,
                    notes="Test-seeded audio MediaAsset.",
                )
            )
    outcome = repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID, media_asset_id=media_asset_id,
        detection=AcousticDetectionFacts(
            common_name=common_name, scientific_name=scientific_name, confidence=0.9,
            window_start_ms=0, window_end_ms=3000,
        ),
        model_provenance={"model": "birdnet-test"}, observed_at=observed_at,
        adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )
    assert outcome.outcome == "created"
    return outcome.visit_id


def test_soundscape_summary_reflects_real_visual_and_acoustic_visits(repository: ProductRepository) -> None:
    _activate(repository)
    _create_visual_visit(repository, proposal_id="p-soundscape-visual", observed_at=NOW)
    cardinal_id = _seed_audio_and_create_acoustic_visit(
        repository, media_asset_id="media-soundscape-1", common_name="Northern Cardinal",
        scientific_name="Cardinalis cardinalis", observed_at=NOW.replace(hour=7),
    )
    chickadee_id = _seed_audio_and_create_acoustic_visit(
        repository, media_asset_id="media-soundscape-2", common_name="Black-capped Chickadee",
        scientific_name="Poecile atricapillus", observed_at=NOW.replace(hour=7, minute=30),
    )
    assert cardinal_id != chickadee_id

    summary = repository.soundscape_summary(
        start_at=NOW.replace(hour=0, minute=0), end_at=NOW.replace(hour=0, minute=0) + timedelta(days=1),
    )

    assert summary.acoustic_encounter_count == 2
    assert summary.visual_only_count == 1
    assert summary.acoustic_only_count == 2
    assert summary.multimodal_count == 0
    hour_7 = next((e for e in summary.hourly_acoustic_activity if e.hour == 7), None)
    assert hour_7 is not None
    assert hour_7.encounter_count == 2


def test_soundscape_summary_period_is_exclusive_of_end(repository: ProductRepository) -> None:
    _activate(repository)
    _seed_audio_and_create_acoustic_visit(
        repository, media_asset_id="media-soundscape-3", common_name="House Wren",
        scientific_name="Troglodytes aedon", observed_at=NOW,
    )
    summary = repository.soundscape_summary(start_at=NOW, end_at=NOW)
    assert summary.acoustic_encounter_count == 0


def test_soundscape_summary_reflects_multimodal_association(repository: ProductRepository) -> None:
    _activate(repository)
    _create_visual_visit(repository, proposal_id="p-soundscape-mm", observed_at=NOW)
    _seed_audio_and_create_acoustic_visit(
        repository, media_asset_id="media-soundscape-mm", common_name="Northern Cardinal",
        scientific_name="Cardinalis cardinalis", observed_at=NOW + timedelta(seconds=3),
    )
    summary = repository.soundscape_summary(
        start_at=NOW - timedelta(hours=1), end_at=NOW + timedelta(hours=1),
    )
    assert summary.multimodal_count == 2  # the visual Visit and the acoustic Visit each count once
    assert summary.visual_only_count == 0
    assert summary.acoustic_only_count == 0
