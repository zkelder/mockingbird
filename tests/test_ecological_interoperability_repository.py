"""Repository-integration tests for Ecological Interoperability &
Submission Workflows v1 (see docs/ecological-interoperability-submission-
v1-contract.md).

Uses an isolated `tmp_path` SQLite database and real candidate-Visit
admission (`create_candidate_visit_from_proposal`) for every test -- never
the real product database -- mirroring `tests/test_research_export_
repository.py`'s established fixture convention exactly. A fake
`TaxonomyLookupRequester` is injected everywhere: these tests never open a
real socket.
"""

from __future__ import annotations

import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from mockingbird.api.schemas import (
    CurrentUser,
    EcologicalEligibilityPreviewRequest,
    EcologicalLocationInput,
    EnvironmentalContextSettingsUpdate,
    ExportEcologicalSubmissionsRequest,
    PrepareEcologicalSubmissionsRequest,
    RecordEcologicalSubmissionResultRequest,
    ResearchExportFilters,
    ReviewCorrectionCreate,
    UserRole,
    VisitReviewRevisionCreate,
    ZoneType,
    ZoneUpdate,
)
from mockingbird.ecological.inaturalist_taxonomy import TaxonomyLookupUnavailableError
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    ProductRepository,
)

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
NOW = datetime(2026, 8, 8, 12, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"


class _FakeTaxonomyRequester:
    """A deterministic, network-free stand-in for iNaturalist's live taxa
    search -- keyed by the exact query text a call is expected to use."""

    def __init__(self, responses: dict[str, list[dict]] | None = None, *, raises: bool = False):
        self._responses = responses or {}
        self._raises = raises
        self.requested_urls: list[str] = []

    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        self.requested_urls.append(url)
        if self._raises:
            raise TaxonomyLookupUnavailableError("simulated network failure")
        for query_text, results in self._responses.items():
            if f"q={query_text.replace(' ', '+')}" in url or f"q={query_text.replace(' ', '%20')}" in url:
                return json.dumps({"results": results}).encode("utf-8")
        return json.dumps({"results": []}).encode("utf-8")


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
        research_export_root=tmp_path / "research_exports",
        ecological_export_root=tmp_path / "ecological_exports",
        inaturalist_taxonomy_requester=_FakeTaxonomyRequester(
            {
                "Northern Cardinal": [
                    {"id": 9083, "name": "Cardinalis cardinalis", "preferred_common_name": "Northern Cardinal"}
                ],
                "Squirrel": [
                    {"id": 1, "name": "Sciurus carolinensis", "preferred_common_name": "Eastern Gray Squirrel"},
                    {"id": 2, "name": "Sciurus niger", "preferred_common_name": "Fox Squirrel"},
                ],
            }
        ),
    )
    yield repo
    repo.close()


def _facts(
    *, proposal_id: str = "visit-episode:fixture-1", zone_id: str | None = FEEDER_ZONE_ID,
) -> CandidateVisitProposalFacts:
    return CandidateVisitProposalFacts(
        proposal_id=proposal_id, stream_id=STREAM_ID, zone_id=zone_id, broad_class="animal",
        start_offset_ms=0, end_offset_ms=4500, constituent_generation_ids=("gen-1", "gen-2"),
        constituent_track_ids=("track-1", "track-2"), source_capture_frame_ids=("frame-1", "frame-2"),
        supporting_frame_ids=("frame-1", "frame-2"), evidence_candidate_ids=("shadow-burst:hash-1",),
        limitation_facts=(), ambiguous_adjacent_proposal_ids=(), concurrent_sibling_proposal_ids=(),
        assembler_version="tracklet-visit-assembler-v1", detector_provenance="onnx-cuda",
        tracker_provenance="frame-driven-onnx-cuda-v1", provider_key="frame-driven-onnx-cuda",
        confidence_evidence_json=None,
    )


def _evidence(role: str = "identification", *, captured_at: datetime | None = NOW) -> CandidateEvidenceItem:
    return CandidateEvidenceItem(
        engine_media_id="shadow-burst:hash-1", role=role, content=JPEG_BYTES, content_type="image/jpeg",
        width=1920, height=1080, captured_at=captured_at, subject_geometry=(0.4, 0.4, 0.6, 0.6),
        geometry_attribution_json=None,
    )


def _activate(repository: ProductRepository, *, now: datetime = NOW) -> None:
    repository.set_observation_authority_mode(
        ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=now, fresh_session=True,
    )


def _create_visit(
    repository: ProductRepository, *, proposal_id: str = "visit-episode:fixture-1",
    zone_id: str | None = FEEDER_ZONE_ID, observed_at: datetime = NOW,
) -> str:
    outcome = repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(proposal_id=proposal_id, zone_id=zone_id),
            observed_at=observed_at, evidence_items=(_evidence(),),
        )
    )
    assert outcome.outcome == "created", outcome.reason
    assert outcome.visit_id is not None
    return outcome.visit_id


def _review(repository: ProductRepository, visit_id: str, label: str, *, origin: str | None = "human") -> None:
    result = repository.create_review_label(
        ReviewCorrectionCreate(
            target_type="visit", target_id=visit_id, label=label, review_origin=origin,
            reviewer_identity="jane researcher",
        ),
        created_at=NOW,
    )
    assert result.review_label.label == label


def _revise(repository: ProductRepository, *, visit_id: str, label: str) -> None:
    """A real, later human correction of an already-reviewed Visit -- mirrors
    `tests/test_historical_baseline_repository.py`'s identical `_revise`
    convention exactly."""

    with repository.session_factory() as session:
        token = repository._review_state_token(session, "visit", visit_id)
    repository.revise_visit_review(
        visit_id,
        VisitReviewRevisionCreate(
            label=label, expected_state_token=token, idempotency_key=f"revise-{visit_id}-{label}",
            review_origin="human", reviewer_identity="jane researcher",
        ),
    )


def _acting_user() -> CurrentUser:
    return CurrentUser(
        id="user-test-admin", display_name="Test Admin", login_identity="test-admin",
        role=UserRole.administrator, enabled=True,
    )


# --- eligibility -------------------------------------------------------


def test_confirmed_named_taxon_with_a_resolved_mapping_is_eligible(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    preview = repository.ecological_eligibility_preview(
        EcologicalEligibilityPreviewRequest(destination="inaturalist")
    )
    item = next(i for i in preview.items if i.visit_id == visit_id)
    assert item.status == "eligible"
    assert preview.eligible_count == 1


def test_confirmed_unidentified_wildlife_is_eligible_for_inaturalist_never_needing_a_mapping(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "unknown_bird")

    preview = repository.ecological_eligibility_preview(
        EcologicalEligibilityPreviewRequest(destination="inaturalist")
    )
    item = next(i for i in preview.items if i.visit_id == visit_id)
    assert item.status == "eligible"


def test_provisional_suggestion_only_is_excluded(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    # No review at all -- stays needs_review with no suggestion -> unresolved,
    # a required-reasons exclusion identical to the research-export gate.
    preview = repository.ecological_eligibility_preview(
        EcologicalEligibilityPreviewRequest(destination="inaturalist")
    )
    item = next(i for i in preview.items if i.visit_id == visit_id)
    assert item.status == "excluded"
    assert "not_yet_reviewed" in item.excluded_reasons


def test_rejected_false_positive_is_excluded(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "false_positive")

    preview = repository.ecological_eligibility_preview(
        EcologicalEligibilityPreviewRequest(destination="inaturalist")
    )
    item = next(i for i in preview.items if i.visit_id == visit_id)
    assert item.status == "excluded"
    assert "rejected_false_positive" in item.excluded_reasons


def test_privacy_zone_reclassification_excludes_from_ecological_eligibility_too(
    repository: ProductRepository,
) -> None:
    """The same real, previously-found gap the research-export foundation
    closed (a Zone reclassified to privacy after a Visit exists under it)
    must be honored here too -- this milestone reuses that eligibility gate
    unmodified rather than re-deriving it."""

    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    preview = repository.ecological_eligibility_preview(
        EcologicalEligibilityPreviewRequest(destination="inaturalist")
    )
    assert next(i for i in preview.items if i.visit_id == visit_id).status == "eligible"

    repository.update_zone(FEEDER_ZONE_ID, ZoneUpdate(zone_type=ZoneType.privacy))

    preview = repository.ecological_eligibility_preview(
        EcologicalEligibilityPreviewRequest(destination="inaturalist")
    )
    item = next(i for i in preview.items if i.visit_id == visit_id)
    assert item.status == "excluded"
    assert "privacy_restricted" in item.excluded_reasons


def test_ebird_excludes_every_record_regardless_of_review_quality(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    preview = repository.ecological_eligibility_preview(EcologicalEligibilityPreviewRequest(destination="ebird"))
    assert preview.destination.offered is False
    item = next(i for i in preview.items if i.visit_id == visit_id)
    assert item.status == "excluded"
    assert item.excluded_reasons == ["destination_not_offered"]


def test_ambiguous_common_name_needs_input_never_a_guessed_mapping(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "squirrel")

    preview = repository.ecological_eligibility_preview(
        EcologicalEligibilityPreviewRequest(destination="inaturalist")
    )
    item = next(i for i in preview.items if i.visit_id == visit_id)
    assert item.status == "needs_input"
    assert "taxonomy_mapping_ambiguous" in item.needs_input_reasons


# --- taxonomy mapping cache ---------------------------------------------


def test_taxonomy_mapping_is_resolved_once_and_reused_from_cache(repository: ProductRepository) -> None:
    _activate(repository)
    visit_a = _create_visit(repository, proposal_id="visit-episode:a")
    visit_b = _create_visit(repository, proposal_id="visit-episode:b")
    _review(repository, visit_a, "northern_cardinal")
    _review(repository, visit_b, "northern_cardinal")

    scoped_filters = ResearchExportFilters(taxon_labels=["northern_cardinal"])
    repository.ecological_eligibility_preview(
        EcologicalEligibilityPreviewRequest(destination="inaturalist", filters=scoped_filters)
    )
    first_call_count = len(repository._inaturalist_taxonomy_requester.requested_urls)
    assert first_call_count == 1  # one distinct label across two Visits, resolved once, not twice

    # A second, later preview call reuses the durable cache -- no new network call.
    repository.ecological_eligibility_preview(
        EcologicalEligibilityPreviewRequest(destination="inaturalist", filters=scoped_filters)
    )
    assert len(repository._inaturalist_taxonomy_requester.requested_urls) == first_call_count


def test_a_lookup_failure_degrades_honestly_and_never_poisons_the_cache(tmp_path: Path) -> None:
    repo = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media",
        research_export_root=tmp_path / "research_exports", ecological_export_root=tmp_path / "ecological_exports",
        inaturalist_taxonomy_requester=_FakeTaxonomyRequester(raises=True),
    )
    try:
        _activate(repo)
        visit_id = _create_visit(repo)
        _review(repo, visit_id, "northern_cardinal")

        preview = repo.ecological_eligibility_preview(EcologicalEligibilityPreviewRequest(destination="inaturalist"))
        item = next(i for i in preview.items if i.visit_id == visit_id)
        assert item.status == "needs_input"
        assert "taxonomy_mapping_unresolved" in item.needs_input_reasons
    finally:
        repo.close()


# --- location: never the weather coordinate -----------------------------


def test_prepare_never_silently_uses_the_configured_weather_coordinate(repository: ProductRepository) -> None:
    repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=40.0, longitude=-105.0, weather_enabled=False),
        acting_user=_acting_user(),
    )
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    records = repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(visit_ids=[visit_id], destination="inaturalist")
    )
    assert records[0].location_choice == "none"
    assert records[0].location_latitude is None
    assert records[0].location_longitude is None


def test_prepare_with_an_explicit_exact_location_carries_it_through(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    records = repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(
            visit_ids=[visit_id], destination="inaturalist",
            location=EcologicalLocationInput(choice="exact", latitude=40.015, longitude=-105.2705),
        )
    )
    assert records[0].location_choice == "exact"
    assert records[0].location_latitude == 40.015
    assert records[0].status == "prepared"


# --- prepare / export / idempotency / correction -------------------------


def test_prepare_is_idempotent_updating_the_same_record_not_duplicating(repository: ProductRepository) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    first = repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(visit_ids=[visit_id], destination="inaturalist")
    )
    second = repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(visit_ids=[visit_id], destination="inaturalist")
    )
    assert first[0].id == second[0].id
    assert len(repository.list_ecological_submissions(visit_id=visit_id)) == 1


def test_correcting_the_reviewed_label_after_preparing_marks_the_record_stale(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    record = repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(visit_ids=[visit_id], destination="inaturalist")
    )[0]
    assert record.is_stale is False

    _revise(repository, visit_id=visit_id, label="blue_jay")

    refreshed = repository.get_ecological_submission(record.id)
    assert refreshed.is_stale is True


def test_export_excludes_a_stale_record_rather_than_silently_exporting_old_truth(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    record = repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(visit_ids=[visit_id], destination="inaturalist")
    )[0]
    _revise(repository, visit_id=visit_id, label="blue_jay")

    result = repository.export_ecological_submissions(ExportEcologicalSubmissionsRequest(submission_ids=[record.id]))
    assert result.included_count == 0
    assert result.skipped[0].reason == "stale_since_prepared"
    assert result.output_directory is None


def test_export_produces_a_real_csv_file_in_the_confirmed_inaturalist_shape(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")

    record = repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(
            visit_ids=[visit_id], destination="inaturalist",
            location=EcologicalLocationInput(choice="exact", latitude=40.0, longitude=-105.0),
        )
    )[0]
    result = repository.export_ecological_submissions(ExportEcologicalSubmissionsRequest(submission_ids=[record.id]))
    assert result.included_count == 1
    assert result.output_directory is not None
    csv_text = (Path(result.output_directory) / "inaturalist_import.csv").read_text()
    assert csv_text.splitlines()[0] == (
        "species_guess,observed_on_string,description,place_guess,latitude,longitude,tags,geoprivacy"
    )
    assert "Cardinalis cardinalis" in csv_text

    refreshed = repository.get_ecological_submission(record.id)
    assert refreshed.status == "exported"
    assert refreshed.exported_at is not None


def test_export_is_idempotent_re_exporting_unchanged_records_succeeds_again(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")
    record = repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(visit_ids=[visit_id], destination="inaturalist")
    )[0]

    first = repository.export_ecological_submissions(ExportEcologicalSubmissionsRequest(submission_ids=[record.id]))
    second = repository.export_ecological_submissions(ExportEcologicalSubmissionsRequest(submission_ids=[record.id]))
    assert first.included_count == 1
    assert second.included_count == 1
    assert first.output_directory != second.output_directory  # a fresh, distinctly-named export each time


def test_recording_an_external_result_never_stores_a_credential_and_preserves_it_on_reprepare(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")
    record = repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(visit_ids=[visit_id], destination="inaturalist")
    )[0]

    submitted = repository.record_ecological_submission_result(
        record.id,
        RecordEcologicalSubmissionResultRequest(
            external_id="98765", external_url="https://www.inaturalist.org/observations/98765",
        ),
    )
    assert submitted.status == "submitted"
    assert submitted.external_id == "98765"

    # Re-preparing the same Visit/destination must never overwrite the
    # already-submitted record's external link (Phase 19/32) -- a fresh,
    # separate record is created instead.
    _revise(repository, visit_id=visit_id, label="blue_jay")
    repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(visit_ids=[visit_id], destination="inaturalist")
    )
    still_submitted = repository.get_ecological_submission(record.id)
    assert still_submitted.external_id == "98765"
    all_records = repository.list_ecological_submissions(visit_id=visit_id)
    assert len(all_records) == 2


def test_no_camera_credential_or_local_path_ever_appears_in_a_submission_record(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")
    record = repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(visit_ids=[visit_id], destination="inaturalist")
    )[0]
    dumped = record.model_dump_json()
    assert "/home/" not in dumped
    assert "rtsp://" not in dumped
    assert "password" not in dumped.lower()


def test_a_user_supplied_place_name_starting_with_a_formula_character_is_neutralized_in_the_csv(
    repository: ProductRepository,
) -> None:
    """Phase 39 security review: CSV injection. A malicious/accidental
    `place_name` like `=cmd|'/c calc'!A1` must never reach the exported CSV
    as a live formula a spreadsheet application would execute on open."""

    _activate(repository)
    visit_id = _create_visit(repository)
    _review(repository, visit_id, "northern_cardinal")
    record = repository.prepare_ecological_submissions(
        PrepareEcologicalSubmissionsRequest(
            visit_ids=[visit_id], destination="inaturalist",
            location=EcologicalLocationInput(
                choice="exact", latitude=40.0, longitude=-105.0, place_name="=cmd|'/c calc'!A1",
            ),
        )
    )[0]
    result = repository.export_ecological_submissions(ExportEcologicalSubmissionsRequest(submission_ids=[record.id]))
    with (Path(result.output_directory) / "inaturalist_import.csv").open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["place_guess"] == "'=cmd|'/c calc'!A1"
    assert not rows[0]["place_guess"].startswith("=")
    # A real negative coordinate must round-trip byte-for-byte, never gain a
    # spurious quote prefix just because it starts with "-" (a genuine
    # regression an earlier version of the fix introduced -- caught here).
    assert rows[0]["longitude"] == "-105.000000"
