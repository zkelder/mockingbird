"""Acoustic / BirdNET Observation Foundation v1 -- real-model Tier 3
acceptance. Genuine, not-faked proof against the real, optional
`classifier-birdnet` dependency stack and a real, positively-identified
field recording -- mirrors this codebase's established `test_bioclip_
runtime.py`/`test_local_product_packaging.py` convention: `skipif`-gated
on real local artifact presence, skipped (never failed) on a build host
that lacks it, and marked `slow` (real model load + real inference,
comfortably beyond ordinary Fast/Core budget) so Fast/Core select around
it while `scripts/verify_full.py`/plain `pytest` still exercise it
opportunistically wherever the artifacts are present.

Real audio fixture provenance: tests/fixtures/acoustic/PROVENANCE.md.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from mockingbird.api.schemas import ReviewCorrectionCreate
from mockingbird.observation import acoustic_ingest
from mockingbird.repository.product_repository import (
    MediaAssetModel,
    ProductRepository,
    SourceProviderConfigurationModel,
)
from mockingbird.species.birdnet_adapter import get_birdnet_status

pytestmark = pytest.mark.slow

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "acoustic"
CARDINAL_FIXTURE = FIXTURE_DIR / "northern_cardinal_48k_mono_15s.wav"
NOISE_FIXTURE = FIXTURE_DIR / "no_bird_synthetic_noise_48k_mono_10s.wav"

STREAM_ID = "stream-backyard-feeder"

_runtime_status = get_birdnet_status()

requires_real_birdnet_and_fixtures = pytest.mark.skipif(
    not _runtime_status.runtime_available or not CARDINAL_FIXTURE.is_file() or not NOISE_FIXTURE.is_file(),
    reason=(
        "requires the real, optional classifier-birdnet dependency stack "
        "and real local fixtures under tests/fixtures/acoustic/ (see "
        "PROVENANCE.md) -- both genuinely absent on an ordinary build host"
    ),
)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    # Pre-Release Trust & Correctness Correction v1 (UI-01): this file's
    # fixtures build Visits on the seeded demo Source's own STREAM_ID, which
    # Dashboard/Bird Log now correctly exclude from real history like every
    # other surface (see `_real_source_condition` in product_repository.py).
    # "De-demo" the seeded Source in place -- the same real-product
    # mechanism (an effective, non-"demo" provider configuration)
    # `_real_source_condition` already recognizes for a Source repurposed
    # after creation.
    with repo.session_factory() as session:
        with session.begin():
            session.add(
                SourceProviderConfigurationModel(
                    source_id="source-backyard-demo", provider_key="manual_upload",
                    config_json="{}", updated_at=datetime.now(UTC),
                )
            )
    yield repo
    repo.close()


def _seed_audio_media_asset(repository: ProductRepository, *, media_asset_id: str, audio_path: Path) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_asset_id, source_id="source-backyard-demo", stream_id=STREAM_ID,
                    filename=audio_path.name, content_type="audio/wav", media_type="audio",
                    local_path=str(audio_path), original_filename=audio_path.name,
                    file_size_bytes=audio_path.stat().st_size, created_at=datetime.now(UTC),
                )
            )


@requires_real_birdnet_and_fixtures
class TestRealBirdNetAcceptance:
    def test_real_positive_recording_reaches_a_confirmed_bird_log_entry(
        self, repository: ProductRepository,
    ) -> None:
        """The full, real, end-to-end contract this milestone exists to
        prove: audio -> BirdNET suggestion -> evidence -> review ->
        authoritative Observation -> Bird Log/Today."""

        _seed_audio_media_asset(repository, media_asset_id="media-real-cardinal", audio_path=CARDINAL_FIXTURE)

        result = acoustic_ingest.run_acoustic_analysis(repository, media_asset_id="media-real-cardinal")

        assert result.status == "completed"
        assert result.detections_above_threshold > 0
        assert result.visits_created == 1

        visit = repository.get_visit(result.visit_ids[0])
        assert visit.species_guess == "northern_cardinal"
        assert visit.review_status.value == "needs_review"

        suggestion = repository.list_species_suggestions(visit_id=result.visit_ids[0])[0]
        assert suggestion.adapter_id == "birdnet"
        assert suggestion.suggested_common_name == "Northern Cardinal"
        assert suggestion.suggested_scientific_name == "Cardinalis cardinalis"
        assert suggestion.confidence is not None and suggestion.confidence > 0.5
        assert suggestion.model_provenance["model_version"] == "BirdNET_GLOBAL_6K_V2.4"
        assert suggestion.model_provenance["source_content_sha256"] is not None

        # Review -> authoritative Observation.
        correction = repository.create_review_label(
            ReviewCorrectionCreate(
                target_type="visit", target_id=visit.id, label="northern_cardinal", review_origin="human",
            )
        )
        assert correction.review_label.is_authoritative is True

        # -> Bird Log / Today, completely unmodified consuming code.
        from mockingbird.api.schemas import WildlifeJournalOverviewRequest

        journal = repository.wildlife_journal_overview(WildlifeJournalOverviewRequest())
        assert any(label.label == "northern_cardinal" for label in journal.labels)

        dashboard = repository.dashboard_summary()
        matching = [v for v in dashboard.recent_activity if v.id == visit.id]
        assert len(matching) == 1
        assert matching[0].primary_evidence.content_type == "audio/wav"

    def test_real_negative_recording_produces_zero_visits_honestly(
        self, repository: ProductRepository,
    ) -> None:
        """The required negative/uncertain case: real BirdNET inference
        against audio with no bird content abstains cleanly -- no
        fabricated species claim, no Visit, an honest recorded run."""

        _seed_audio_media_asset(repository, media_asset_id="media-real-noise", audio_path=NOISE_FIXTURE)

        result = acoustic_ingest.run_acoustic_analysis(repository, media_asset_id="media-real-noise")

        assert result.status == "completed"
        assert result.visits_created == 0
        assert result.detections_above_threshold == 0
        assert result.windows_analyzed > 0  # real inference genuinely ran

        runs = repository.list_acoustic_analysis_runs_for_media_asset("media-real-noise")
        assert runs[0].status == "completed"
        assert runs[0].detections_above_threshold == 0
