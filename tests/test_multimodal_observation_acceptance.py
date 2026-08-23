"""Multimodal Observation & Soundscape v1, Phase M: the deterministic
multimodal acceptance corpus and the nine mandatory acceptance scenarios
(see docs/multimodal-observation-soundscape-v1-contract.md).

Exercises the real, unmodified production paths -- `create_candidate_visit_
from_proposal` (visual) and `create_acoustic_candidate_visit`/`extend_
acoustic_candidate_visit` (acoustic) -- against an isolated `tmp_path`
SQLite database, never the real product database (see
docs/test-repository-isolation-contract.md). BirdNET/MDv5 inference itself
is out of scope here (already proven elsewhere -- `tests/test_birdnet_
adapter.py`, `tests/test_acoustic_ingest_real_model.py`,
`tests/test_candidate_visit_repository.py`); this file proves what happens
*after* a detection already exists, which is what the multimodal
association engine actually reasons about.

One real audio fixture is used where it materially matters for the
scenario it documents (`tests/fixtures/acoustic/overlapping_cardinal_
chickadee_48k_mono_derived.wav` for Scenario 7 -- an actually-overlapping
two-species clip built for exactly this purpose). Timing relationships
between visual and acoustic evidence are otherwise synthesized
deterministically via `observed_at`, matching the documented "synthetic
timing alignment is acceptable" hardware boundary -- no physical
colocated camera+microphone exists yet to measure real clock alignment.

This is an acceptance corpus, not a research-grade multimodal benchmark.
"""

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
    VisitModel,
)
from mockingbird.api.schemas import ReviewCorrectionCreate

STREAM_ID = "stream-backyard-feeder"
FEEDER_ZONE_ID = "zone-feeder"
NOW = datetime(2026, 8, 22, 9, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"
REAL_OVERLAPPING_FIXTURE = (
    Path(__file__).parent / "fixtures" / "acoustic" / "overlapping_cardinal_chickadee_48k_mono_derived.wav"
)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _activate(repository: ProductRepository, *, now: datetime = NOW) -> None:
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=now)


def _visual_facts(*, proposal_id: str, concurrent_sibling_proposal_ids: tuple[str, ...] = ()) -> CandidateVisitProposalFacts:
    return CandidateVisitProposalFacts(
        proposal_id=proposal_id, stream_id=STREAM_ID, zone_id=FEEDER_ZONE_ID, broad_class="bird",
        start_offset_ms=0, end_offset_ms=2000,
        constituent_generation_ids=("gen-1",), constituent_track_ids=("track-1",),
        source_capture_frame_ids=("frame-1",), supporting_frame_ids=("frame-1",),
        evidence_candidate_ids=(f"shadow-burst:{proposal_id}",), limitation_facts=(),
        ambiguous_adjacent_proposal_ids=(), concurrent_sibling_proposal_ids=concurrent_sibling_proposal_ids,
        assembler_version="tracklet-visit-assembler-v1", detector_provenance="onnx-cuda",
        tracker_provenance="frame-driven-onnx-cuda-v1", provider_key="frame-driven-onnx-cuda",
        confidence_evidence_json=None,
    )


def _visual_evidence(proposal_id: str) -> tuple[CandidateEvidenceItem, ...]:
    return (
        CandidateEvidenceItem(
            engine_media_id=f"shadow-burst:{proposal_id}", role="identification", content=JPEG_BYTES,
            content_type="image/jpeg", width=1920, height=1080, captured_at=NOW,
            subject_geometry=(0.4, 0.4, 0.6, 0.6), geometry_attribution_json=None,
        ),
    )


def _create_visual_visit(repository: ProductRepository, *, proposal_id: str, observed_at: datetime, sibling_ids: tuple[str, ...] = ()):
    return repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_visual_facts(proposal_id=proposal_id, concurrent_sibling_proposal_ids=sibling_ids),
            observed_at=observed_at, evidence_items=_visual_evidence(proposal_id),
        )
    )


def _seed_audio_media_asset(repository: ProductRepository, *, media_asset_id: str, captured_at: datetime, local_path: str | None = None) -> None:
    with repository.session_factory() as session:
        with session.begin():
            session.add(
                MediaAssetModel(
                    id=media_asset_id, source_id="source-backyard-demo", stream_id=STREAM_ID,
                    filename=f"{media_asset_id}.wav", content_type="audio/wav", media_type="audio",
                    local_path=local_path or f"/tmp/{media_asset_id}.wav", original_filename=f"{media_asset_id}.wav",
                    file_size_bytes=1024, created_at=datetime.now(UTC),
                    captured_at=captured_at, notes="Acceptance-corpus-seeded audio MediaAsset.",
                )
            )


def _create_acoustic_visit(
    repository: ProductRepository, *, media_asset_id: str, common_name: str, scientific_name: str,
    observed_at: datetime, window_start_ms: int = 0, window_end_ms: int = 3000, confidence: float = 0.9,
):
    return repository.create_acoustic_candidate_visit(
        stream_id=STREAM_ID, media_asset_id=media_asset_id,
        detection=AcousticDetectionFacts(
            common_name=common_name, scientific_name=scientific_name, confidence=confidence,
            window_start_ms=window_start_ms, window_end_ms=window_end_ms,
        ),
        model_provenance={"model": "birdnet-test", "version": "acceptance-corpus"},
        observed_at=observed_at, adapter_id="birdnet", adapter_name="BirdNET-Analyzer",
    )


def _set_species_guess(repository: ProductRepository, visit_id: str, label: str) -> None:
    with repository.session_factory() as session:
        with session.begin():
            visit = session.get(VisitModel, visit_id)
            assert visit is not None
            visit.species_guess = label


def _confirm(repository: ProductRepository, visit_id: str, label: str) -> None:
    result = repository.create_review_label(
        ReviewCorrectionCreate(target_type="visit", target_id=visit_id, label=label, review_origin="human"),
    )
    assert result is not None


# --- Scenario 1: agreement --------------------------------------------------


def test_scenario_1_agreement_visual_and_acoustic_same_species_strongly_overlapping(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    visual_outcome = _create_visual_visit(repository, proposal_id="p-scenario-1", observed_at=NOW)
    assert visual_outcome.outcome == "created"

    _seed_audio_media_asset(repository, media_asset_id="media-scenario-1", captured_at=NOW)
    acoustic_outcome = _create_acoustic_visit(
        repository, media_asset_id="media-scenario-1", common_name="Northern Cardinal",
        scientific_name="Cardinalis cardinalis", observed_at=NOW + timedelta(seconds=2),
    )
    assert acoustic_outcome.outcome == "created"

    acoustic_visit = repository.get_visit(acoustic_outcome.visit_id)
    assert acoustic_visit is not None
    _set_species_guess(repository, visual_outcome.visit_id, acoustic_visit.species_guess)

    # Association occurs, agreement is represented.
    visual_associations = repository.multimodal_associations_for_visit(visual_outcome.visit_id)
    assert len(visual_associations) == 1
    assert visual_associations[0].tier == "associated"
    assert visual_associations[0].other_modality == "acoustic"
    assert visual_associations[0].taxon_agreement == "agrees"
    assert visual_associations[0].other_visit.id == acoustic_outcome.visit_id

    # Both evidence sources are retained independently.
    assert repository.get_visit(visual_outcome.visit_id) is not None
    assert repository.get_visit(acoustic_outcome.visit_id) is not None
    assert len(repository.visit_evidence_frames(visual_outcome.visit_id)) >= 1
    assert len(repository.visit_evidence_frames(acoustic_outcome.visit_id)) >= 1

    # Observation remains provisional until review.
    visual_visit = repository.get_visit(visual_outcome.visit_id)
    assert visual_visit.review_status == "needs_review"
    assert visual_visit.reviewed_label is None

    # Human confirmation makes it authoritative.
    _confirm(repository, visual_outcome.visit_id, acoustic_visit.species_guess)
    reviewed_visual_visit = repository.get_visit(visual_outcome.visit_id)
    assert reviewed_visual_visit.review_status == "reviewed"
    assert reviewed_visual_visit.reviewed_label == acoustic_visit.species_guess


# --- Scenario 2: conflict ----------------------------------------------------


def test_scenario_2_conflict_visual_and_acoustic_disagree_overlapping(repository: ProductRepository) -> None:
    _activate(repository)
    visual_outcome = _create_visual_visit(repository, proposal_id="p-scenario-2", observed_at=NOW)
    _set_species_guess(repository, visual_outcome.visit_id, "house_finch")

    _seed_audio_media_asset(repository, media_asset_id="media-scenario-2", captured_at=NOW)
    acoustic_outcome = _create_acoustic_visit(
        repository, media_asset_id="media-scenario-2", common_name="Carolina Wren",
        scientific_name="Thryothorus ludovicianus", observed_at=NOW + timedelta(seconds=3),
    )

    associations = repository.multimodal_associations_for_visit(visual_outcome.visit_id)
    assert len(associations) == 1
    # No silent automatic winner: association still occurs (they are
    # genuinely temporally related) but agreement honestly reports a
    # conflict rather than picking one suggestion.
    assert associations[0].tier == "associated"
    assert associations[0].taxon_agreement == "differs"

    # Both suggestions remain visible.
    visual_visit = repository.get_visit(visual_outcome.visit_id)
    acoustic_visit = repository.get_visit(acoustic_outcome.visit_id)
    assert visual_visit.species_guess == "house_finch"
    assert acoustic_visit.species_guess != "house_finch"

    # Review resolves the identity -- correction propagates to the
    # authoritative Visit regardless of which suggestion it matches.
    _confirm(repository, visual_outcome.visit_id, acoustic_visit.species_guess)
    resolved = repository.get_visit(visual_outcome.visit_id)
    assert resolved.review_status == "reviewed"
    assert resolved.reviewed_label == acoustic_visit.species_guess


# --- Scenario 3: visual only -------------------------------------------------


def test_scenario_3_visual_only_behavior_unchanged(repository: ProductRepository) -> None:
    _activate(repository)
    outcome = _create_visual_visit(repository, proposal_id="p-scenario-3", observed_at=NOW)

    assert outcome.outcome == "created"
    assert repository.multimodal_associations_for_visit(outcome.visit_id) == []
    visit = repository.get_visit(outcome.visit_id)
    assert visit.review_status == "needs_review"


# --- Scenario 4: audio only ---------------------------------------------------


def test_scenario_4_audio_only_behavior_unchanged_and_described_as_heard(repository: ProductRepository) -> None:
    _seed_audio_media_asset(repository, media_asset_id="media-scenario-4", captured_at=NOW)
    outcome = _create_acoustic_visit(
        repository, media_asset_id="media-scenario-4", common_name="House Wren",
        scientific_name="Troglodytes aedon", observed_at=NOW,
    )

    assert outcome.outcome == "created"
    assert repository.multimodal_associations_for_visit(outcome.visit_id) == []
    visit = repository.get_visit(outcome.visit_id)
    assert visit.review_status == "needs_review"
    frames = repository.visit_evidence_frames(outcome.visit_id)
    assert len(frames) >= 1
    assert all(frame.content_type.startswith("audio/") for frame in frames)


# --- Scenario 5: temporal coincidence but independent ------------------------


def test_scenario_5_temporally_near_but_independent_events_are_not_collapsed(repository: ProductRepository) -> None:
    _activate(repository)
    visual_outcome = _create_visual_visit(repository, proposal_id="p-scenario-5", observed_at=NOW)

    # Ten minutes later -- well outside even the wider "possible" window.
    _seed_audio_media_asset(repository, media_asset_id="media-scenario-5", captured_at=NOW + timedelta(minutes=10))
    acoustic_outcome = _create_acoustic_visit(
        repository, media_asset_id="media-scenario-5", common_name="American Robin",
        scientific_name="Turdus migratorius", observed_at=NOW + timedelta(minutes=10),
    )

    assert repository.multimodal_associations_for_visit(visual_outcome.visit_id) == []
    assert repository.multimodal_associations_for_visit(acoustic_outcome.visit_id) == []


def test_scenario_5b_boundary_just_past_possible_window_is_independent(repository: ProductRepository) -> None:
    """Proves the 60s possible-window threshold is a real, enforced boundary
    -- not an accident of a much-larger test gap."""

    _activate(repository)
    visual_outcome = _create_visual_visit(repository, proposal_id="p-scenario-5b", observed_at=NOW)
    _seed_audio_media_asset(repository, media_asset_id="media-scenario-5b", captured_at=NOW + timedelta(seconds=61))
    acoustic_outcome = _create_acoustic_visit(
        repository, media_asset_id="media-scenario-5b", common_name="Blue Jay",
        scientific_name="Cyanocitta cristata", observed_at=NOW + timedelta(seconds=61),
    )
    assert repository.multimodal_associations_for_visit(visual_outcome.visit_id) == []
    assert repository.multimodal_associations_for_visit(acoustic_outcome.visit_id) == []


def test_scenario_5c_boundary_within_possible_but_not_strict_window_is_possible_not_associated(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    visual_outcome = _create_visual_visit(repository, proposal_id="p-scenario-5c", observed_at=NOW)
    _seed_audio_media_asset(repository, media_asset_id="media-scenario-5c", captured_at=NOW + timedelta(seconds=45))
    _create_acoustic_visit(
        repository, media_asset_id="media-scenario-5c", common_name="Song Sparrow",
        scientific_name="Melospiza melodia", observed_at=NOW + timedelta(seconds=45),
    )
    associations = repository.multimodal_associations_for_visit(visual_outcome.visit_id)
    assert len(associations) == 1
    assert associations[0].tier == "possible"


# --- Scenario 6: multiple visual subjects ------------------------------------


def test_scenario_6_acoustic_evidence_not_blindly_assigned_to_every_visual_subject(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    bird_a = _create_visual_visit(repository, proposal_id="p-scenario-6-a", observed_at=NOW, sibling_ids=("p-scenario-6-b",))
    bird_b = _create_visual_visit(repository, proposal_id="p-scenario-6-b", observed_at=NOW, sibling_ids=("p-scenario-6-a",))
    assert bird_a.outcome == "created"
    assert bird_b.outcome == "created"
    # Genuinely one shared encounter: both subjects share one Event.
    assert bird_a.event_id == bird_b.event_id

    _seed_audio_media_asset(repository, media_asset_id="media-scenario-6", captured_at=NOW + timedelta(seconds=4))
    acoustic_outcome = _create_acoustic_visit(
        repository, media_asset_id="media-scenario-6", common_name="Tufted Titmouse",
        scientific_name="Baeolophus bicolor", observed_at=NOW + timedelta(seconds=4),
    )

    bird_a_associations = repository.multimodal_associations_for_visit(bird_a.visit_id)
    bird_b_associations = repository.multimodal_associations_for_visit(bird_b.visit_id)

    # Both see the acoustic evidence as a *possible* relationship...
    assert len(bird_a_associations) == 1
    assert len(bird_b_associations) == 1
    assert bird_a_associations[0].tier == "possible"
    assert bird_b_associations[0].tier == "possible"
    # ...never as a confidently claimed identity for either specific subject.
    assert "associated" not in {bird_a_associations[0].tier, bird_b_associations[0].tier}

    acoustic_associations = repository.multimodal_associations_for_visit(acoustic_outcome.visit_id)
    assert {a.other_visit.id for a in acoustic_associations} == {bird_a.visit_id, bird_b.visit_id}


def test_scenario_6b_late_arriving_sibling_downgrades_a_stale_associated_row(
    repository: ProductRepository,
) -> None:
    """The harder ordering Scenario 6's main test does not naturally
    exercise: the acoustic detection arrives *between* the two visual
    siblings' own creation, so the first sibling is briefly, honestly
    "associated" with it -- alone, correctly, at that moment. When the
    second sibling then joins the same Event, reconciliation must
    downgrade that now-stale claim to "possible" rather than leaving a
    confident relationship standing that a second subject just made
    genuinely ambiguous (see `ProductRepository._reconcile_multimodal_
    association_for_event`'s own "always a full recomputation" docstring)."""

    _activate(repository)
    bird_a = _create_visual_visit(repository, proposal_id="p-scenario-6b-a", observed_at=NOW, sibling_ids=("p-scenario-6b-b",))

    _seed_audio_media_asset(repository, media_asset_id="media-scenario-6b", captured_at=NOW + timedelta(seconds=4))
    acoustic_outcome = _create_acoustic_visit(
        repository, media_asset_id="media-scenario-6b", common_name="Carolina Chickadee",
        scientific_name="Poecile carolinensis", observed_at=NOW + timedelta(seconds=4),
    )

    # At this moment, exactly one visual subject is known -- honestly
    # associated, alone.
    interim = repository.multimodal_associations_for_visit(bird_a.visit_id)
    assert len(interim) == 1
    assert interim[0].tier == "associated"
    interim_association_id = interim[0].association_id

    # A second subject now joins the same encounter.
    bird_b = _create_visual_visit(repository, proposal_id="p-scenario-6b-b", observed_at=NOW, sibling_ids=("p-scenario-6b-a",))
    assert bird_b.event_id == bird_a.event_id

    bird_a_after = repository.multimodal_associations_for_visit(bird_a.visit_id)
    bird_b_after = repository.multimodal_associations_for_visit(bird_b.visit_id)

    assert len(bird_a_after) == 1
    assert bird_a_after[0].association_id == interim_association_id  # upserted, not duplicated
    assert bird_a_after[0].tier == "possible"  # downgraded, not left stale
    assert len(bird_b_after) == 1
    assert bird_b_after[0].tier == "possible"
    assert bird_b_after[0].other_visit.id == acoustic_outcome.visit_id


# --- Scenario 7: multiple acoustic species -----------------------------------


def test_scenario_7_two_acoustic_species_in_one_window_both_survive_and_associate(
    repository: ProductRepository,
) -> None:
    """Reuses the real overlapping two-species fixture clip for provenance
    (see module docstring) -- the repository call itself is exercised
    directly, exactly as the automatic acoustic runtime's own admit-
    detection callback would call it once BirdNET has already produced two
    same-window, different-species detections from this file."""

    _activate(repository)
    visual_outcome = _create_visual_visit(repository, proposal_id="p-scenario-7", observed_at=NOW)

    local_path = str(REAL_OVERLAPPING_FIXTURE) if REAL_OVERLAPPING_FIXTURE.exists() else None
    _seed_audio_media_asset(
        repository, media_asset_id="media-scenario-7", captured_at=NOW + timedelta(seconds=1), local_path=local_path,
    )
    cardinal_outcome = _create_acoustic_visit(
        repository, media_asset_id="media-scenario-7", common_name="Northern Cardinal",
        scientific_name="Cardinalis cardinalis", observed_at=NOW + timedelta(seconds=1),
        window_start_ms=0, window_end_ms=3000,
    )
    chickadee_outcome = _create_acoustic_visit(
        repository, media_asset_id="media-scenario-7", common_name="Black-capped Chickadee",
        scientific_name="Poecile atricapillus", observed_at=NOW + timedelta(seconds=1),
        window_start_ms=0, window_end_ms=3000,
    )

    # The Phase B fix: both survive independently, not the second silently
    # collapsed into the first's idempotent-repeat outcome.
    assert cardinal_outcome.outcome == "created"
    assert chickadee_outcome.outcome == "created"
    assert cardinal_outcome.visit_id != chickadee_outcome.visit_id

    visual_associations = repository.multimodal_associations_for_visit(visual_outcome.visit_id)
    assert {a.other_visit.id for a in visual_associations} == {cardinal_outcome.visit_id, chickadee_outcome.visit_id}
    # From each acoustic Visit's own perspective there is exactly one
    # visual candidate in range, so each independently resolves cleanly.
    assert all(a.tier == "associated" for a in visual_associations)


# --- Scenario 8: reviewed correction -----------------------------------------


def test_scenario_8_human_correction_becomes_authoritative_and_is_never_overwritten(
    repository: ProductRepository,
) -> None:
    _activate(repository)
    visual_outcome = _create_visual_visit(repository, proposal_id="p-scenario-8", observed_at=NOW)
    _set_species_guess(repository, visual_outcome.visit_id, "northern_cardinal")

    _seed_audio_media_asset(repository, media_asset_id="media-scenario-8", captured_at=NOW)
    acoustic_outcome = _create_acoustic_visit(
        repository, media_asset_id="media-scenario-8", common_name="Northern Cardinal",
        scientific_name="Cardinalis cardinalis", observed_at=NOW + timedelta(seconds=1),
    )
    acoustic_visit_before = repository.get_visit(acoustic_outcome.visit_id)
    assert acoustic_visit_before.species_guess == "northern_cardinal"  # models agree on A

    # Human determines it is actually a different species (B).
    _confirm(repository, visual_outcome.visit_id, "house_finch")
    reviewed = repository.get_visit(visual_outcome.visit_id)
    assert reviewed.reviewed_label == "house_finch"

    # A second acoustic detection arrives nearby -- association/inference
    # runs again (this is exactly what "later inference/association" means
    # here) but must never overwrite the human correction.
    _seed_audio_media_asset(repository, media_asset_id="media-scenario-8b", captured_at=NOW + timedelta(seconds=2))
    _create_acoustic_visit(
        repository, media_asset_id="media-scenario-8b", common_name="Northern Cardinal",
        scientific_name="Cardinalis cardinalis", observed_at=NOW + timedelta(seconds=2),
    )
    still_reviewed = repository.get_visit(visual_outcome.visit_id)
    assert still_reviewed.reviewed_label == "house_finch"
    assert still_reviewed.review_status == "reviewed"

    # The acoustic Visit's own independent suggestion is untouched too --
    # correction propagates to what was corrected, never fabricates
    # agreement by silently rewriting the other modality's own evidence.
    acoustic_visit_after = repository.get_visit(acoustic_outcome.visit_id)
    assert acoustic_visit_after.species_guess == "northern_cardinal"
    assert acoustic_visit_after.review_status == "needs_review"


# --- Scenario 9: restart / idempotency ---------------------------------------


def test_scenario_9_reassociation_after_restart_is_deterministic_and_creates_no_duplicates(
    repository: ProductRepository, tmp_path: Path,
) -> None:
    _activate(repository)
    visual_outcome = _create_visual_visit(repository, proposal_id="p-scenario-9", observed_at=NOW)
    _seed_audio_media_asset(repository, media_asset_id="media-scenario-9", captured_at=NOW)
    acoustic_outcome = _create_acoustic_visit(
        repository, media_asset_id="media-scenario-9", common_name="Downy Woodpecker",
        scientific_name="Dryobates pubescens", observed_at=NOW + timedelta(seconds=3),
    )

    first_pass = repository.multimodal_associations_for_visit(visual_outcome.visit_id)
    assert len(first_pass) == 1
    first_association_id = first_pass[0].association_id
    first_tier = first_pass[0].tier

    # Simulate a process restart: a brand-new `ProductRepository` instance
    # against the exact same database file, then re-run the association
    # reconciliation step directly -- the same mechanism a future restart-
    # recovery sweep would invoke.
    db_path = repository.db_url
    restarted = ProductRepository(db_url=db_path, media_root=repository.media_root)
    try:
        with restarted.session_factory() as session:
            with session.begin():
                event = session.get(VisitModel, visual_outcome.visit_id)
                restarted._reconcile_multimodal_association_for_event(
                    session, event_id=event.event_id, now=NOW,
                )

        second_pass = restarted.multimodal_associations_for_visit(visual_outcome.visit_id)
        assert len(second_pass) == 1  # no duplicate row
        assert second_pass[0].association_id == first_association_id  # same identity, upserted not re-created
        assert second_pass[0].tier == first_tier  # deterministic
        assert second_pass[0].other_visit.id == acoustic_outcome.visit_id
    finally:
        restarted.close()
