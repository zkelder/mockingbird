"""Multimodal Observation & Soundscape v1, Phase B: species-scoped acoustic
candidate idempotency regression tests.

Before this fix, `create_acoustic_candidate_visit`/`extend_acoustic_
candidate_visit` deduplicated on `(media_asset_id, window_start_ms,
window_end_ms, adapter_id)` -- no species column. Two distinct species
genuinely detected in the identical merged BirdNET window (plausible: two
birds calling at once, both windows merged to the same start/end by
`acoustic_ingest._merge_same_species_detections`) collided: the second
species' insert matched the first species' already-persisted row and was
silently returned as `"idempotent_repeat"` -- no second Visit, no Event, no
error, no log. Every test below constructs that exact collision shape
directly at the repository layer (no ffmpeg/BirdNET model dependency) and
would fail under the old 4-column key."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from mockingbird.repository.product_repository import (
    AcousticDetectionFacts,
    MediaAssetModel,
    ProductRepository,
)

STREAM_ID = "stream-backyard-feeder"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _seed_audio_media_asset(repository: ProductRepository, *, media_asset_id: str, captured_at: datetime) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_asset_id, source_id="source-backyard-demo", stream_id=STREAM_ID,
                    filename=f"{media_asset_id}.wav", content_type="audio/wav", media_type="audio",
                    local_path=f"/tmp/{media_asset_id}.wav", original_filename=f"{media_asset_id}.wav",
                    file_size_bytes=1024, created_at=datetime.now(UTC),
                    captured_at=captured_at, notes="Test-seeded audio MediaAsset.",
                )
            )


CARDINAL = AcousticDetectionFacts(
    common_name="Northern Cardinal", scientific_name="Cardinalis cardinalis",
    confidence=0.91, window_start_ms=0, window_end_ms=3000,
)
CHICKADEE = AcousticDetectionFacts(
    common_name="Black-capped Chickadee", scientific_name="Poecile atricapillus",
    confidence=0.88, window_start_ms=0, window_end_ms=3000,
)


def test_two_distinct_species_in_the_identical_window_both_create_visits(
    repository: ProductRepository,
) -> None:
    """The core regression: two different species, byte-identical
    (media_asset_id, window_start_ms, window_end_ms, adapter_id) -- must
    both become independent candidate Visits, not the second silently
    dropped as an idempotent repeat of the first."""

    _seed_audio_media_asset(repository, media_asset_id="media-audio-1", captured_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC))

    cardinal_outcome = repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID, media_asset_id="media-audio-1", detection=CARDINAL,
        model_provenance={"model": "birdnet-test"}, observed_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
        adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )
    chickadee_outcome = repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID, media_asset_id="media-audio-1", detection=CHICKADEE,
        model_provenance={"model": "birdnet-test"}, observed_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
        adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )

    assert cardinal_outcome.outcome == "created"
    assert chickadee_outcome.outcome == "created"  # <-- was "idempotent_repeat" under the old key
    assert cardinal_outcome.visit_id != chickadee_outcome.visit_id
    assert cardinal_outcome.event_id != chickadee_outcome.event_id
    assert cardinal_outcome.species_suggestion_id != chickadee_outcome.species_suggestion_id

    cardinal_visit = repository.get_visit(cardinal_outcome.visit_id)
    chickadee_visit = repository.get_visit(chickadee_outcome.visit_id)
    assert cardinal_visit is not None and chickadee_visit is not None
    assert cardinal_visit.species_guess != chickadee_visit.species_guess


def test_same_species_same_window_retry_is_still_idempotent(repository: ProductRepository) -> None:
    """The fix must not weaken the case it is supposed to keep working:
    retrying the exact same detection (e.g. a caller re-running analysis
    under an unchanged pipeline) still returns the original Visit, never a
    duplicate."""

    _seed_audio_media_asset(repository, media_asset_id="media-audio-1", captured_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC))

    first = repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID, media_asset_id="media-audio-1", detection=CARDINAL,
        model_provenance={"model": "birdnet-test"}, observed_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
        adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )
    retry = repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID, media_asset_id="media-audio-1", detection=CARDINAL,
        model_provenance={"model": "birdnet-test"}, observed_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
        adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )

    assert first.outcome == "created"
    assert retry.outcome == "idempotent_repeat"
    assert retry.visit_id == first.visit_id
    assert retry.event_id == first.event_id
    assert retry.species_suggestion_id == first.species_suggestion_id


def test_extend_also_species_scopes_idempotency(repository: ProductRepository) -> None:
    """The same collision shape, reached through `extend_acoustic_candidate_
    visit` instead of `create` -- a second cross-segment clip carrying two
    distinct species at the identical (new) window, each extending its own
    distinct, already-existing same-species Visit."""

    _seed_audio_media_asset(repository, media_asset_id="media-audio-1", captured_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC))
    cardinal_first = repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID, media_asset_id="media-audio-1", detection=CARDINAL,
        model_provenance={"model": "birdnet-test"}, observed_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
        adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )
    chickadee_first = repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID, media_asset_id="media-audio-1", detection=CHICKADEE,
        model_provenance={"model": "birdnet-test"}, observed_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
        adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )

    # A second, later segment: both species continue calling, merged to the
    # identical new window on the identical new media asset.
    _seed_audio_media_asset(repository, media_asset_id="media-audio-2", captured_at=datetime(2026, 8, 22, 9, 0, 3, tzinfo=UTC))

    cardinal_extended = repository.extend_acoustic_candidate_visit(
        visit_id=cardinal_first.visit_id, event_id=cardinal_first.event_id, stream_id=STREAM_ID,
        media_asset_id="media-audio-2", detection=CARDINAL, model_provenance={"model": "birdnet-test"},
        observed_at=datetime(2026, 8, 22, 9, 0, 3, tzinfo=UTC), adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )
    chickadee_extended = repository.extend_acoustic_candidate_visit(
        visit_id=chickadee_first.visit_id, event_id=chickadee_first.event_id, stream_id=STREAM_ID,
        media_asset_id="media-audio-2", detection=CHICKADEE, model_provenance={"model": "birdnet-test"},
        observed_at=datetime(2026, 8, 22, 9, 0, 3, tzinfo=UTC), adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )

    assert cardinal_extended.outcome == "extended"
    assert chickadee_extended.outcome == "extended"  # <-- was "idempotent_repeat" pointing at the cardinal's own row
    assert cardinal_extended.visit_id == cardinal_first.visit_id
    assert chickadee_extended.visit_id == chickadee_first.visit_id
    assert cardinal_extended.species_suggestion_id != chickadee_extended.species_suggestion_id


def test_database_level_unique_index_rejects_a_true_duplicate(repository: ProductRepository, tmp_path: Path) -> None:
    """Defense in depth: the raw SQL unique index itself, not just the
    application-level SELECT-before-INSERT, refuses a genuine duplicate
    5-tuple insert."""

    _seed_audio_media_asset(repository, media_asset_id="media-audio-1", captured_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC))
    outcome = repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID, media_asset_id="media-audio-1", detection=CARDINAL,
        model_provenance={"model": "birdnet-test"}, observed_at=datetime(2026, 8, 22, 9, 0, tzinfo=UTC),
        adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )
    # Read back the real `suggested_label` this install's taxonomy resolved
    # `detection.common_name` to (never hardcode/guess it -- it may or may
    # not be taxonomy-normalized depending on seed data), so this insert
    # collides on the *actual* stored 5-tuple, not an assumed one.
    created_visit = repository.get_visit(outcome.visit_id)
    assert created_visit is not None and created_visit.species_guess is not None

    with pytest.raises(IntegrityError):
        with repository.session_factory() as session:
            with session.begin():
                session.execute(
                    text(
                        "INSERT INTO species_suggestions "
                        "(id, adapter_id, adapter_name, suggested_label, rank, alternatives_json, status, "
                        "created_at, media_asset_id, window_start_ms, window_end_ms) "
                        "VALUES ('species-suggestion-duplicate', 'birdnet', 'BirdNET-Analyzer', "
                        ":label, 1, '[]', 'pending', :now, 'media-audio-1', 0, 3000)"
                    ),
                    {"now": datetime.now(UTC), "label": created_visit.species_guess},
                )
