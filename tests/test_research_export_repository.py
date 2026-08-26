"""Repository-integration tests for Research / Conservation / Export
Interoperability v1 (see docs/research-conservation-export-contract.md).

Uses an isolated `tmp_path` SQLite database and real candidate-Visit
admission (`create_candidate_visit_from_proposal`) for every test -- never
the real product database -- mirroring the established
`tests/test_candidate_visit_repository.py` fixture convention exactly.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from mockingbird.api.schemas import (
    CamtrapDpExportRequest,
    ConservationReportRequest,
    ReviewCorrectionCreate,
    ResearchCollectionCreate,
    ResearchExportFilters,
    ResearchExportRequest,
    SpeciesSuggestionCreateRequest,
)
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.repository.product_repository import (
    AcousticDetectionFacts,
    CameraSourceModel,
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    EventModel,
    MediaAssetModel,
    ProductRepository,
    StreamModel,
    VisitModel,
)

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
        research_export_root=tmp_path / "research_exports",
    )
    yield repo
    repo.close()


def _facts(
    *,
    proposal_id: str = "visit-episode:fixture-1",
    zone_id: str | None = FEEDER_ZONE_ID,
    provider_key: str = "frame-driven-onnx-cuda",
    concurrent_sibling_proposal_ids: tuple[str, ...] = (),
) -> CandidateVisitProposalFacts:
    return CandidateVisitProposalFacts(
        proposal_id=proposal_id,
        stream_id=STREAM_ID,
        zone_id=zone_id,
        broad_class="animal",
        start_offset_ms=0,
        end_offset_ms=4500,
        constituent_generation_ids=("gen-1", "gen-2"),
        constituent_track_ids=("track-1", "track-2"),
        source_capture_frame_ids=("frame-1", "frame-2"),
        supporting_frame_ids=("frame-1", "frame-2"),
        evidence_candidate_ids=("shadow-burst:hash-1",),
        limitation_facts=(),
        ambiguous_adjacent_proposal_ids=(),
        concurrent_sibling_proposal_ids=concurrent_sibling_proposal_ids,
        assembler_version="tracklet-visit-assembler-v1",
        detector_provenance="onnx-cuda",
        tracker_provenance="frame-driven-onnx-cuda-v1",
        provider_key=provider_key,
        confidence_evidence_json=None,
    )


def _evidence(
    role: str = "identification",
    *,
    captured_at: datetime | None = NOW,
    resolution_provenance: str | None = None,
) -> CandidateEvidenceItem:
    geometry_json = (
        f'{{"resolution_provenance": "{resolution_provenance}"}}' if resolution_provenance else None
    )
    return CandidateEvidenceItem(
        engine_media_id="shadow-burst:hash-1",
        role=role,
        content=JPEG_BYTES,
        content_type="image/jpeg",
        width=1920,
        height=1080,
        captured_at=captured_at,
        subject_geometry=(0.4, 0.4, 0.6, 0.6),
        geometry_attribution_json=geometry_json,
    )


def _activate(repository: ProductRepository, *, now: datetime = NOW, fresh_session: bool = True) -> None:
    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=now, fresh_session=fresh_session,
    )


def _create_visit(
    repository: ProductRepository,
    *,
    proposal_id: str = "visit-episode:fixture-1",
    observed_at: datetime = NOW,
    provider_key: str = "frame-driven-onnx-cuda",
    captured_at: datetime | None = NOW,
    concurrent_sibling_proposal_ids: tuple[str, ...] = (),
) -> str:
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(
                proposal_id=proposal_id, provider_key=provider_key,
                concurrent_sibling_proposal_ids=concurrent_sibling_proposal_ids,
            ),
            observed_at=observed_at,
            evidence_items=(_evidence(captured_at=captured_at),),
        )
    )
    assert outcome.outcome == "created", outcome.reason
    assert outcome.visit_id is not None
    return outcome.visit_id


def _review(
    repository: ProductRepository, visit_id: str, label: str, *, origin: str | None = "human",
    reviewer_identity: str | None = "jane researcher", created_at: datetime = NOW,
) -> None:
    result = repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=visit_id, label=label,
            review_origin=origin, reviewer_identity=reviewer_identity,
        ),
        created_at=created_at,
    )
    assert result.review_label.label == label


# --- eligibility / classification (regressions #1, #2, #5, #6, #7) ---------


def test_confirmed_reviewed_taxon_is_eligible_for_trusted_export(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    observations, excluded = repository.research_export_eligibility_preview(ResearchExportFilters())
    matching = [obs for obs in observations if obs.observation_id == visit_id]
    assert len(matching) == 1
    observation = matching[0]
    assert observation.classification == "confirmed_taxon"
    assert observation.eligibility.eligible is True
    assert observation.taxon_label == "northern_cardinal"
    assert observation.taxon_display_name == "Northern Cardinal"
    # The seeded demo repository already carries its own needs-review Visit;
    # this assertion is about *this* Visit never contributing an exclusion,
    # not about a pristine empty database.
    assert visit_id not in {obs.observation_id for obs in observations if not obs.eligibility.eligible}


def test_provisional_suggestion_alone_is_not_trusted_named_taxon(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    repository.create_species_suggestion(
        SpeciesSuggestionCreateRequest(
            visit_id=visit_id, adapter_id="bioclip", adapter_name="bioclip",
            suggested_label="house_finch", confidence=0.7,
        )
    )

    observations, excluded = repository.research_export_eligibility_preview(ResearchExportFilters())
    observation = next(obs for obs in observations if obs.observation_id == visit_id)
    assert observation.classification == "provisional_suggestion"
    assert observation.eligibility.eligible is False
    assert excluded.get("provisional_suggestion_only") == 1


def test_confirmed_unidentified_wildlife_is_represented_honestly(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "unknown_bird")

    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    observation = next(obs for obs in observations if obs.observation_id == visit_id)
    assert observation.classification == "confirmed_unidentified_wildlife"
    assert observation.eligibility.eligible_as_unidentified_wildlife is True
    # "unknown_bird" is itself a real, non-species taxonomy row (confirmed
    # wildlife, species honestly abstained) -- never a fabricated species
    # name or scientific name.
    assert observation.taxon_label == "unknown_bird"
    assert observation.is_species is False
    assert observation.taxon_scientific_name is None


def test_privacy_zone_reclassification_withholds_export(repository: ProductRepository) -> None:
    from mockingbird.api.schemas import ZoneUpdate, ZoneType

    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    # Confirm it is eligible before the Zone is reclassified.
    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    assert next(obs for obs in observations if obs.observation_id == visit_id).eligibility.eligible is True

    repository.update_zone(FEEDER_ZONE_ID, ZoneUpdate(zone_type=ZoneType.privacy))

    observations, excluded = repository.research_export_eligibility_preview(ResearchExportFilters())
    observation = next(obs for obs in observations if obs.observation_id == visit_id)
    assert observation.eligibility.eligible is False
    assert "privacy_restricted" in observation.eligibility.required_reasons
    assert excluded.get("privacy_restricted") == 1


def test_no_camera_credential_or_local_path_ever_appears_in_an_observation(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    observation = next(obs for obs in observations if obs.observation_id == visit_id)
    payload = str(observation.__dict__) + str([e.__dict__ for e in observation.evidence])
    assert str(repository.media_root) not in payload
    assert "://" not in payload or "camera_node" in payload  # no embedded connection URL


# --- corrections / supersession (regressions #3, #4, #28) ------------------


def test_corrected_review_changes_exported_taxon(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")
    _review(repository, visit_id, "house_finch", created_at=NOW)

    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    observation = next(obs for obs in observations if obs.observation_id == visit_id)
    assert observation.taxon_label == "house_finch"


def test_structurally_superseded_visit_is_excluded_from_current_export(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    with repository.session_factory() as session:
        with session.begin():
            visit_model = session.get(VisitModel, visit_id)
            visit_model.is_superseded = True

    observations, excluded = repository.research_export_eligibility_preview(ResearchExportFilters())
    assert all(obs.observation_id != visit_id for obs in observations)


def test_capture_time_reflects_historical_observed_at_never_import_wall_clock(
    repository: ProductRepository,
) -> None:
    # An offline-provider Visit whose real encounter happened years ago
    # (`observed_at`) must export under that real historical timestamp, not
    # under whatever wall-clock moment the analysis/export actually ran --
    # mirroring offline_ingest's own "a historical clip imported today is
    # never reported as observed today" invariant at this layer's own
    # `captured_at` field.
    historical_observed_at = datetime(2020, 3, 14, 9, 30, tzinfo=UTC)
    # Offline ingest activates authority fresh for its own bounded call at
    # the moment analysis actually runs (see "Acquisition-session
    # semantics" in docs/offline-recorded-media-observation-contract.md) --
    # the activation boundary itself is a real "now," but the candidate's
    # own `observed_at` still legitimately reflects the video's historical
    # timeline, exactly like a real offline-ingest run.
    _activate(repository, now=historical_observed_at)
    visit_id = _create_visit(
        repository, proposal_id="visit-episode:historical", provider_key="recorded-media-offline-ingest-v1",
        observed_at=historical_observed_at, captured_at=historical_observed_at,
    )
    _review(repository, visit_id, "northern_cardinal")

    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    observation = next(obs for obs in observations if obs.observation_id == visit_id)
    assert observation.captured_at == historical_observed_at
    assert observation.captured_at.year == 2020
    assert observation.captured_at != datetime.now(UTC).replace(microsecond=0)


def test_offline_reanalysis_does_not_duplicate_current_reviewed_truth(repository: ProductRepository) -> None:
    # Idempotent repeat: attempting the identical proposal_id twice must
    # never create a second Visit for the same underlying encounter.
    _activate(repository)
    visit_id_1 = _create_visit(repository, proposal_id="visit-episode:idempotent")
    _review(repository, visit_id_1, "northern_cardinal")
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id="visit-episode:idempotent"),
            observed_at=NOW,
            evidence_items=(_evidence(),),
        )
    )
    assert outcome.outcome == "idempotent_repeat"

    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    assert sum(1 for obs in observations if obs.observation_id == visit_id_1) == 1


# --- acquisition provenance / timestamps (regressions #12, #13, #14, #15) --


def test_camera_node_rtsp_onvif_and_offline_records_share_one_export_schema(repository: ProductRepository) -> None:
    _activate(repository)
    live_visit_id = _create_visit(repository, proposal_id="visit-episode:live", provider_key="frame-driven-onnx-cuda")
    offline_visit_id = _create_visit(
        repository, proposal_id="visit-episode:offline", provider_key="recorded-media-offline-ingest-v1",
    )
    _review(repository, live_visit_id, "northern_cardinal")
    _review(repository, offline_visit_id, "house_finch")

    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    live = next(obs for obs in observations if obs.observation_id == live_visit_id)
    offline = next(obs for obs in observations if obs.observation_id == offline_visit_id)
    assert type(live) is type(offline)  # one shared ResearchObservation shape
    assert live.acquisition_type == "continuous_live"
    assert live.is_offline_acquisition is False
    assert offline.acquisition_type == "recorded_video"
    assert offline.is_offline_acquisition is True


def test_capture_timestamp_confidence_reflects_whether_real_capture_time_was_known(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    known_visit_id = _create_visit(repository, proposal_id="visit-episode:known-time", captured_at=NOW)
    unknown_visit_id = _create_visit(repository, proposal_id="visit-episode:unknown-time", captured_at=None)
    _review(repository, known_visit_id, "northern_cardinal")
    _review(repository, unknown_visit_id, "house_finch")

    observations, excluded = repository.research_export_eligibility_preview(ResearchExportFilters())
    known = next(obs for obs in observations if obs.observation_id == known_visit_id)
    unknown = next(obs for obs in observations if obs.observation_id == unknown_visit_id)
    assert known.capture_timestamp_confidence == "recorded"
    assert unknown.capture_timestamp_confidence == "unknown"
    # Still eligible -- an uncertain timestamp is a recommended gap, not a blocker.
    assert unknown.eligibility.eligible is True
    assert "capture_timestamp_uncertain" in unknown.eligibility.recommended_reasons


def test_source_resolution_provenance_is_retained(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")
    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    observation = next(obs for obs in observations if obs.observation_id == visit_id)
    assert len(observation.evidence) >= 1
    assert observation.evidence[0].width == 1920
    assert observation.evidence[0].height == 1080


# --- multi-subject (regression #11) -----------------------------------------


def test_multi_subject_event_exports_separate_subject_observations(repository: ProductRepository) -> None:
    _activate(repository)
    first_id = _create_visit(
        repository, proposal_id="visit-episode:sibling-a",
        concurrent_sibling_proposal_ids=("visit-episode:sibling-b",),
    )
    second_id = _create_visit(
        repository, proposal_id="visit-episode:sibling-b",
        concurrent_sibling_proposal_ids=("visit-episode:sibling-a",),
    )
    _review(repository, first_id, "northern_cardinal")
    _review(repository, second_id, "house_finch")

    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    first = next(obs for obs in observations if obs.observation_id == first_id)
    second = next(obs for obs in observations if obs.observation_id == second_id)
    assert first.event_id == second.event_id  # one shared Event
    assert first.observation_id != second.observation_id  # two distinct Observations
    assert {first.taxon_label, second.taxon_label} == {"northern_cardinal", "house_finch"}


# --- Multimodal Observation & Soundscape v1, Phase L ------------------------


def _seed_audio_media_asset(repository: ProductRepository, *, media_asset_id: str, captured_at: datetime) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_asset_id, source_id="source-backyard-demo", stream_id=STREAM_ID,
                    filename=f"{media_asset_id}.wav", content_type="audio/wav", media_type="audio",
                    local_path=f"/tmp/{media_asset_id}.wav", original_filename=f"{media_asset_id}.wav",
                    file_size_bytes=1024, created_at=datetime.now(UTC), captured_at=captured_at,
                    notes="Test-seeded audio MediaAsset.",
                )
            )


def test_export_distinguishes_visual_acoustic_and_multimodal_evidence(repository: ProductRepository) -> None:
    """Phase L: research-safe export can distinguish visual, acoustic, and
    multimodally-associated evidence without ever letting model agreement
    become observational authority -- `evidence_modality`/`multimodal_
    association` are separate, honest facts alongside the unchanged
    reviewed-truth precedence the rest of this test file already proves."""

    _activate(repository)

    visual_only_id = _create_visit(repository, proposal_id="visit-episode:visual-only", observed_at=NOW)

    associated_visual_id = _create_visit(
        repository, proposal_id="visit-episode:multimodal-visual", observed_at=NOW + timedelta(hours=1),
    )
    _seed_audio_media_asset(
        repository, media_asset_id="media-audio-export", captured_at=NOW + timedelta(hours=1, seconds=2),
    )
    acoustic_outcome = repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID, media_asset_id="media-audio-export",
        detection=AcousticDetectionFacts(
            common_name="Northern Cardinal", scientific_name="Cardinalis cardinalis",
            confidence=0.9, window_start_ms=0, window_end_ms=3000,
        ),
        model_provenance={"model": "birdnet-test"}, observed_at=NOW + timedelta(hours=1, seconds=2),
        adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )
    assert acoustic_outcome.outcome == "created"

    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    by_id = {obs.observation_id: obs for obs in observations}

    visual_only = by_id[visual_only_id]
    assert visual_only.evidence_modality == "visual"
    assert visual_only.multimodal_association == "none"

    acoustic_only = by_id[acoustic_outcome.visit_id]
    assert acoustic_only.evidence_modality == "acoustic"

    associated_visual = by_id[associated_visual_id]
    assert associated_visual.evidence_modality == "visual"
    assert associated_visual.multimodal_association == "associated"
    assert acoustic_only.multimodal_association == "associated"

    # Round-trips into the JSON/CSV row shapes without dropping the facts.
    from mockingbird.research.research_export import observation_to_csv_row, observation_to_json

    json_row = observation_to_json(associated_visual)
    assert json_row["evidence_modality"] == "visual"
    assert json_row["multimodal_association"] == "associated"
    csv_row = observation_to_csv_row(associated_visual)
    assert csv_row["evidence_modality"] == "visual"
    assert csv_row["multimodal_association"] == "associated"


# --- filters (regression #25: no-Zone configuration) ------------------------


def test_no_zone_configuration_still_exports_correctly(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository, proposal_id="visit-episode:no-zone")
    with repository.session_factory() as session:
        with session.begin():
            visit_model = session.get(VisitModel, visit_id)
            visit_model.zone_id = None
            event_model = session.get(EventModel, visit_model.event_id)
            event_model.primary_zone_id = None  # StreamVisitSummary falls back to the Event's Zone otherwise
    _review(repository, visit_id, "northern_cardinal")

    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    observation = next(obs for obs in observations if obs.observation_id == visit_id)
    assert observation.zone_id is None
    assert observation.eligibility.eligible is True


# --- generic export (regressions #16, #20, #21) -----------------------------


def test_generic_export_is_deterministic_and_writes_metadata_only_files(
    repository: ProductRepository, tmp_path: Path,
) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    first = repository.export_research_dataset(ResearchExportRequest(output_name="run-one"))
    assert first.dry_run is False
    assert first.observation_count >= 1
    assert first.output_directory is not None
    output_dir = Path(first.output_directory)
    for name in ("observations.csv", "observations.jsonl", "media.csv", "sources.csv", "effort.csv", "manifest.json"):
        assert (output_dir / name).exists()
    observations_csv = (output_dir / "observations.csv").read_text(encoding="utf-8")
    assert "local_path" not in observations_csv
    assert str(repository.media_root) not in observations_csv
    assert visit_id in observations_csv
    assert "northern_cardinal" in observations_csv

    second = repository.export_research_dataset(ResearchExportRequest(output_name="run-two"))
    assert second.manifest.content_fingerprint == first.manifest.content_fingerprint


def test_export_dry_run_writes_no_files(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    response = repository.export_research_dataset(ResearchExportRequest(dry_run=True))
    assert response.dry_run is True
    assert response.output_directory is None
    assert not repository.research_export_root.exists() or not any(repository.research_export_root.iterdir())


def test_research_export_does_not_mutate_product_truth(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    before = repository.analytics_summary()
    repository.export_research_dataset(ResearchExportRequest())
    repository.export_camtrap_dp_package(CamtrapDpExportRequest())
    after = repository.analytics_summary()
    assert before.model_dump() == after.model_dump()


# --- Camtrap DP (regressions #17, #18, #19) ---------------------------------


def test_camtrap_dp_export_produces_internally_valid_references(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    response = repository.export_camtrap_dp_package(CamtrapDpExportRequest())
    assert response.validation.valid is True
    assert response.deployment_count == 1
    assert response.observation_count >= 1
    assert response.profile_version == "1.0.2"


# --- conservation report (regression #8, #9, #10) ---------------------------


def test_conservation_report_reflects_live_effort_and_reviewed_species(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")
    repository.record_observation_exposure_frame(
        stream_id=STREAM_ID, runtime_generation_id="gen-1", healthy_at=NOW, now=NOW,
    )

    report = repository.conservation_report(
        ConservationReportRequest(start_at=datetime(2026, 8, 8, tzinfo=UTC), end_at=datetime(2026, 8, 9, tzinfo=UTC))
    )
    assert report.reviewed_wildlife_visit_count == 1
    assert len(report.confirmed_species) == 1
    assert report.confirmed_species[0].label == "northern_cardinal"
    assert report.live_monitoring_monitored_seconds is not None and report.live_monitoring_monitored_seconds >= 0


def test_conservation_report_never_exposes_a_population_or_percentage_field(repository: ProductRepository) -> None:
    report = repository.conservation_report(
        ConservationReportRequest(start_at=datetime(2026, 8, 8, tzinfo=UTC), end_at=datetime(2026, 8, 9, tzinfo=UTC))
    )
    forbidden = {"population", "abundance", "occupancy", "biodiversity_index", "percentage", "trend"}
    assert forbidden.isdisjoint(set(type(report).model_fields))


def test_conservation_report_default_scope_still_includes_a_camera_archived_afterward(
    repository: ProductRepository,
) -> None:
    """Multi-Camera Place Experience v2: a research/conservation export
    defaulting to "every Stream" (no explicit `stream_ids` filter) must not
    silently drop a retired camera's real reviewed history -- a scientific
    record does not stop being real because the camera that captured it was
    later retired. Archive-only removal never deletes the underlying Visit
    (see camera-source-experience-v1-report.md)."""

    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    with repository.session_factory() as session:
        with session.begin():
            stream = session.get(StreamModel, STREAM_ID)
            assert stream is not None
            source = session.get(CameraSourceModel, stream.source_id)
            assert source is not None
            source.status = "archived"

    report = repository.conservation_report(
        ConservationReportRequest(
            start_at=datetime(2026, 8, 8, tzinfo=UTC), end_at=datetime(2026, 8, 9, tzinfo=UTC)
        )
    )
    assert report.reviewed_wildlife_visit_count == 1
    assert len(report.confirmed_species) == 1
    assert report.confirmed_species[0].label == "northern_cardinal"


# --- collections / contributor attribution (regressions #22, #23, #24) -----


def test_contributor_attribution_is_retained_and_grants_no_review_authority(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal", reviewer_identity="jane researcher")

    collection = repository.create_research_collection(
        ResearchCollectionCreate(
            name="Backyard 2026", curator_identity="jane researcher", visit_ids=[visit_id],
        )
    )
    assert collection.curator_identity == "jane researcher"
    assert collection.eligible_observation_count == 1

    observations, _ = repository.research_export_eligibility_preview(ResearchExportFilters())
    observation = next(obs for obs in observations if obs.observation_id == visit_id)
    assert observation.reviewed_by == "jane researcher"

    # Curating a collection never changes the reviewed taxon or review
    # authority -- the underlying ReviewLabel truth is untouched.
    with repository.session_factory() as session:
        review_labels = session.execute(select(VisitModel).where(VisitModel.id == visit_id)).one()[0]
        assert review_labels.reviewed_label == "northern_cardinal"


def test_collection_manifest_is_reproducible(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")
    collection = repository.create_research_collection(
        ResearchCollectionCreate(name="Reproducible Set", visit_ids=[visit_id])
    )

    first = repository.export_research_dataset(
        ResearchExportRequest(filters=ResearchExportFilters(collection_id=collection.id))
    )
    second = repository.export_research_dataset(
        ResearchExportRequest(filters=ResearchExportFilters(collection_id=collection.id))
    )
    assert first.manifest.content_fingerprint == second.manifest.content_fingerprint
    assert first.observation_count == 1


def test_collection_excludes_a_visit_that_was_never_reviewed(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)  # never reviewed

    collection = repository.create_research_collection(
        ResearchCollectionCreate(name="Mixed Set", visit_ids=[visit_id])
    )
    assert collection.eligible_observation_count == 0
    assert collection.excluded_count == 1
