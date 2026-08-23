"""Camera / Source + Multi-Camera Maturity v1, Phase I: the mandatory
overlapping-camera acceptance journeys (6, 7, 8, 9) against the real,
unmodified `create_candidate_visit_from_proposal` production path and an
isolated `tmp_path` SQLite database -- mirrors `tests/test_candidate_visit_
repository.py`'s `test_multi_stream_authority_is_isolated` for how to add a
second, independent Source/Stream, and `tests/test_multimodal_observation_
acceptance.py` for the overall acceptance-journey shape.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.repository.product_repository import (
    CandidateEvidenceItem,
    CandidateVisitProposalFacts,
    CreateCandidateVisitRequest,
    CrossCameraVisitAssociationModel,
    ProductRepository,
)
from mockingbird.storage.models import CameraSourceModel, StreamModel, ZoneModel

SOURCE_A = "source-camera-a"
STREAM_A = "stream-camera-a"
SOURCE_B = "source-camera-b"
STREAM_B = "stream-camera-b"
ZONE_A = "zone-camera-a-backyard"
ZONE_B_MATCHING = "zone-camera-b-backyard"
ZONE_B_DIFFERENT = "zone-camera-b-driveway"
NOW = datetime(2026, 8, 23, 9, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"0" * 64 + b"\xff\xd9"


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    # Two fully independent, explicitly-created cameras -- deliberately NOT
    # the repository's own pre-seeded demo Stream (`stream-backyard-feeder`,
    # which already carries its own seeded Zone; reusing it here would make
    # `_representative_area_name` ambiguous the moment this fixture adds a
    # second Zone, an entanglement with demo-seed internals this file has no
    # reason to depend on). See docs/test-repository-isolation-contract.md.
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    with repo.session_factory() as session:
        with session.begin():
            session.add(CameraSourceModel(
                id=SOURCE_A, name="Camera A", kind="integration", status="connected",
                description="First fixture camera.",
            ))
            session.add(StreamModel(
                id=STREAM_A, source_id=SOURCE_A, name="Camera A stream",
                description="First fixture Stream.", is_live=True,
            ))
            session.add(CameraSourceModel(
                id=SOURCE_B, name="Camera B", kind="integration", status="connected",
                description="Second, independent fixture camera.",
            ))
            session.add(StreamModel(
                id=STREAM_B, source_id=SOURCE_B, name="Camera B stream",
                description="Second, independent fixture Stream.", is_live=True,
            ))
            # Camera A's own real Zone -- "Backyard feeder" is its one
            # active, non-privacy Zone, so it is an unambiguous
            # representative Area (see `_representative_area_name`).
            session.add(ZoneModel(
                id=ZONE_A, stream_id=STREAM_A, name="Backyard Feeder", zone_type="feeder",
                polygon_json="[]", is_active=True, monitoring_policy_json=None,
            ))
    repo.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_A, now=NOW)
    repo.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_B, now=NOW)
    yield repo
    repo.close()


def _add_zone_b(repository: ProductRepository, *, matching: bool) -> None:
    zone_id = ZONE_B_MATCHING if matching else ZONE_B_DIFFERENT
    name = "Backyard Feeder" if matching else "Driveway"
    with repository.session_factory() as session:
        with session.begin():
            session.add(ZoneModel(
                id=zone_id, stream_id=STREAM_B, name=name, zone_type="feeder",
                polygon_json="[]", is_active=True, monitoring_policy_json=None,
            ))


def _facts(
    *, proposal_id: str, stream_id: str, zone_id: str | None,
    concurrent_sibling_proposal_ids: tuple[str, ...] = (),
) -> CandidateVisitProposalFacts:
    return CandidateVisitProposalFacts(
        proposal_id=proposal_id, stream_id=stream_id, zone_id=zone_id, broad_class="bird",
        start_offset_ms=0, end_offset_ms=2000,
        constituent_generation_ids=("gen-1",), constituent_track_ids=("track-1",),
        source_capture_frame_ids=("frame-1",), supporting_frame_ids=("frame-1",),
        evidence_candidate_ids=(f"shadow-burst:{proposal_id}",), limitation_facts=(),
        ambiguous_adjacent_proposal_ids=(), concurrent_sibling_proposal_ids=concurrent_sibling_proposal_ids,
        assembler_version="tracklet-visit-assembler-v1", detector_provenance="onnx-cuda",
        tracker_provenance="frame-driven-onnx-cuda-v1", provider_key="frame-driven-onnx-cuda",
        confidence_evidence_json=None,
    )


def _evidence(proposal_id: str) -> tuple[CandidateEvidenceItem, ...]:
    return (
        CandidateEvidenceItem(
            engine_media_id=f"shadow-burst:{proposal_id}", role="identification", content=JPEG_BYTES,
            content_type="image/jpeg", width=1920, height=1080, captured_at=NOW,
            subject_geometry=(0.4, 0.4, 0.6, 0.6), geometry_attribution_json=None,
        ),
    )


def _create(
    repository: ProductRepository, *, proposal_id: str, stream_id: str, zone_id: str | None,
    observed_at: datetime, concurrent_sibling_proposal_ids: tuple[str, ...] = (),
):
    return repository.create_candidate_visit_from_proposal(
        CreateCandidateVisitRequest(
            proposal=_facts(
                proposal_id=proposal_id, stream_id=stream_id, zone_id=zone_id,
                concurrent_sibling_proposal_ids=concurrent_sibling_proposal_ids,
            ),
            observed_at=observed_at,
            evidence_items=_evidence(proposal_id),
        )
    )


def _association_rows(repository: ProductRepository) -> list[CrossCameraVisitAssociationModel]:
    with repository.session_factory() as session:
        return list(session.query(CrossCameraVisitAssociationModel).all())


def test_journey7_same_encounter_matching_area_reaches_associated(repository: ProductRepository) -> None:
    """Two cameras, both an unambiguous 'Backyard Feeder' Area, single
    subject each, well within the strict window -> confident association;
    both evidence lineages survive untouched."""

    _add_zone_b(repository, matching=True)
    a = _create(repository, proposal_id="cam-a:1", stream_id=STREAM_A, zone_id=ZONE_A, observed_at=NOW)
    b = _create(
        repository, proposal_id="cam-b:1", stream_id=STREAM_B, zone_id=ZONE_B_MATCHING,
        observed_at=NOW + timedelta(seconds=3),
    )

    rows = _association_rows(repository)
    assert len(rows) == 1
    assert rows[0].tier == "associated"
    assert rows[0].spatial_signal == "matching_area_name"
    assert {rows[0].primary_visit_id, rows[0].secondary_visit_id} == {a.visit_id, b.visit_id}

    # Both sides remain independently, fully resolvable -- never merged.
    associations = repository.cross_camera_associations_for_visit(a.visit_id)
    assert len(associations) == 1
    assert associations[0].other_visit.id == b.visit_id
    assert associations[0].other_source_name == "Camera B"
    assert associations[0].tier == "associated"
    assert repository.get_visit(a.visit_id) is not None
    assert repository.get_visit(b.visit_id) is not None

    # Today's own presentation collapses the confident pair into one row.
    summary = repository.dashboard_summary()
    recent_ids = {item.id for item in summary.recent_activity}
    assert a.visit_id in recent_ids or b.visit_id in recent_ids
    assert not (a.visit_id in recent_ids and b.visit_id in recent_ids), (
        "an associated pair must not read as two independent encounters in Today's recent activity"
    )
    collapsed = next(item for item in summary.recent_activity if item.id in {a.visit_id, b.visit_id})
    assert collapsed.cross_camera_partner is not None
    assert collapsed.cross_camera_partner.tier == "associated"


def test_journey6_independent_encounters_differing_area_no_association(repository: ProductRepository) -> None:
    """Two cameras with confirmed *different* named Areas, close in time ->
    no false merge, and (Journey 6's own no-noise requirement) not even a
    'possible' row -- real evidence of physical separation, not mere
    ambiguity."""

    _add_zone_b(repository, matching=False)
    a = _create(repository, proposal_id="cam-a:2", stream_id=STREAM_A, zone_id=ZONE_A, observed_at=NOW)
    _create(
        repository, proposal_id="cam-b:2", stream_id=STREAM_B, zone_id=ZONE_B_DIFFERENT,
        observed_at=NOW + timedelta(seconds=3),
    )

    assert _association_rows(repository) == []
    assert repository.cross_camera_associations_for_visit(a.visit_id) == []


def test_journey8_ambiguous_overlap_unknown_area_stays_possible(repository: ProductRepository) -> None:
    """Neither camera has an unambiguous Area assigned -- genuinely unknown
    spatial information must stay conservatively 'possible', never merged,
    and never silently dropped either."""

    # No Zone at all on Camera B's Stream -- `_representative_area_name`
    # honestly returns None (zero candidates), not a guess.
    a = _create(repository, proposal_id="cam-a:3", stream_id=STREAM_A, zone_id=ZONE_A, observed_at=NOW)
    b = _create(
        repository, proposal_id="cam-b:3", stream_id=STREAM_B, zone_id=None,
        observed_at=NOW + timedelta(seconds=3),
    )

    rows = _association_rows(repository)
    assert len(rows) == 1
    assert rows[0].tier == "possible"
    assert rows[0].spatial_signal == "unknown"

    # Never collapsed for presentation -- both rows stay independently visible.
    summary = repository.dashboard_summary()
    recent_ids = {item.id for item in summary.recent_activity}
    assert a.visit_id in recent_ids and b.visit_id in recent_ids
    for item in summary.recent_activity:
        if item.id in {a.visit_id, b.visit_id}:
            assert item.cross_camera_partner is None


def test_journey9_multi_subject_camera_a_never_contaminates_camera_b(repository: ProductRepository) -> None:
    """Camera A sees two concurrent birds (multi-subject Event); Camera B
    sees one nearby, matching-Area bird. Prove: no collapse into one
    identity, no evidence assigned to every Camera A subject, conservative
    'possible' for every resulting pair -- not a forced merge."""

    _add_zone_b(repository, matching=True)
    left = _create(
        repository, proposal_id="cam-a:left", stream_id=STREAM_A, zone_id=ZONE_A, observed_at=NOW,
        concurrent_sibling_proposal_ids=("cam-a:right",),
    )
    right = _create(
        repository, proposal_id="cam-a:right", stream_id=STREAM_A, zone_id=ZONE_A, observed_at=NOW,
        concurrent_sibling_proposal_ids=("cam-a:left",),
    )
    assert left.event_id == right.event_id  # two distinct subjects, one shared Event -- the Phase J setup.

    b = _create(
        repository, proposal_id="cam-b:multi", stream_id=STREAM_B, zone_id=ZONE_B_MATCHING,
        observed_at=NOW + timedelta(seconds=3),
    )

    rows = _association_rows(repository)
    # Exactly one row per Camera-A subject x Camera-B visit -- both pairs
    # recorded, neither collapsed to a single identity.
    assert len(rows) == 2
    assert all(row.tier == "possible" for row in rows)
    assert all(row.multi_subject for row in rows)
    pairs = {frozenset((row.primary_visit_id, row.secondary_visit_id)) for row in rows}
    assert pairs == {frozenset((left.visit_id, b.visit_id)), frozenset((right.visit_id, b.visit_id))}

    # Never collapsed for presentation -- a "possible" tier always stays visible.
    summary = repository.dashboard_summary()
    for item in summary.recent_activity:
        if item.id in {left.visit_id, right.visit_id, b.visit_id}:
            assert item.cross_camera_partner is None

    # Each Camera-A subject remains its own independently reviewable Visit
    # -- proximity never became guaranteed identity for either one.
    assert repository.get_visit(left.visit_id).id != repository.get_visit(right.visit_id).id


def test_far_apart_in_time_is_independent_even_with_matching_area(repository: ProductRepository) -> None:
    """A matching Area alone is never sufficient -- far enough apart in time
    is still independent, no row at all."""

    _add_zone_b(repository, matching=True)
    a = _create(repository, proposal_id="cam-a:4", stream_id=STREAM_A, zone_id=ZONE_A, observed_at=NOW)
    _create(
        repository, proposal_id="cam-b:4", stream_id=STREAM_B, zone_id=ZONE_B_MATCHING,
        observed_at=NOW + timedelta(minutes=10),
    )

    assert _association_rows(repository) == []
    assert repository.cross_camera_associations_for_visit(a.visit_id) == []


def test_reconciliation_removes_a_stale_row_when_a_third_closer_candidate_arrives(
    repository: ProductRepository,
) -> None:
    """Full-recompute reconciliation (not an incremental patch): a
    previously-unambiguous pair correctly downgrades from 'associated' to
    'possible' the moment a second, equally-plausible camera-B candidate
    makes it genuinely ambiguous -- mirrors the multimodal engine's own
    Phase H guarantee, extended to cross-camera."""

    _add_zone_b(repository, matching=True)
    a = _create(repository, proposal_id="cam-a:5", stream_id=STREAM_A, zone_id=ZONE_A, observed_at=NOW)
    b1 = _create(
        repository, proposal_id="cam-b:5a", stream_id=STREAM_B, zone_id=ZONE_B_MATCHING,
        observed_at=NOW + timedelta(seconds=3),
    )
    first_rows = _association_rows(repository)
    assert len(first_rows) == 1 and first_rows[0].tier == "associated"

    # A second Source (Camera C), also matching Area, also in range.
    source_c, stream_c, zone_c = "source-camera-c", "stream-camera-c", "zone-camera-c"
    with repository.session_factory() as session:
        with session.begin():
            session.add(CameraSourceModel(
                id=source_c, name="Camera C", kind="integration", status="connected", description="Third camera.",
            ))
            session.add(StreamModel(
                id=stream_c, source_id=source_c, name="Camera C stream", description="Third Stream.", is_live=True,
            ))
            session.add(ZoneModel(
                id=zone_c, stream_id=stream_c, name="Backyard Feeder", zone_type="feeder",
                polygon_json="[]", is_active=True, monitoring_policy_json=None,
            ))
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=stream_c, now=NOW)
    b2 = _create(
        repository, proposal_id="cam-c:5b", stream_id=stream_c, zone_id=zone_c,
        observed_at=NOW + timedelta(seconds=4),
    )

    # Three concurrent, same-Area, in-range camera Events -> all three
    # pairwise combinations are genuinely ambiguous (each competes with the
    # other two), so all three get a "possible" row -- including (b1, b2),
    # which this reconciliation cascade must also correctly pick up even
    # though neither b1 nor b2 was the Visit that directly triggered it.
    rows = _association_rows(repository)
    assert len(rows) == 3
    assert all(row.tier == "possible" for row in rows)  # a<->b1 downgraded from its prior "associated"
    pairs = {frozenset((row.primary_visit_id, row.secondary_visit_id)) for row in rows}
    assert pairs == {
        frozenset((a.visit_id, b1.visit_id)),
        frozenset((a.visit_id, b2.visit_id)),
        frozenset((b1.visit_id, b2.visit_id)),
    }
