"""Independent Corroboration Value & Persistent-Confusor Admission
Correctness v1.

Reopened by real field evidence: Representative Daylight Gate A Field
Acceptance v10 (docs/representative-daylight-gate-a-field-acceptance-v10-
report.md) found the accepted Hard-Negative Visit Admission Precision fix
(`candidate_quality_gate.reject_insufficient_detector_corroboration`)
correctly rejected 3/3 classic bare-minimum single-generation hard
negatives this session, but the *same* recurring tube-feeder-area confusor
defeated the rule's count-based corroboration axis 4 separate times by
accumulating many individually-insufficient detections within one
continuation window -- concretely reproducing the fix's own disclosed
residual ("a hypothetical real bird at the exact same corroboration floor
... is not distinguishable by corroboration structure alone") at real
field scale.

Every reproducer below drives real `DetectionObservation`/`FramePacket`
sequences through the real, unmodified production path -- identical
methodology to `tests/test_hard_negative_visit_admission_precision_v1.py`
(`ProviderNeutralFrameTracker.observe()` -> `build_tracklets`/
`assemble_visit_episodes` -> `CandidateVisitAuthorityAdapter.
attempt_candidate` -> a real, isolated `ProductRepository`) -- never a
fixture that simply declares `is_false = True`. See docs/independent-
corroboration-value-persistent-confusor-admission-correctness-v1-report.md
for the full field-evidence trace, the mathematical derivation ruling out
every raw-count/confidence-magnitude variant, and the locked admission
contract this file exercises.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from mockingbird.observation.candidate_visit_adapter import CandidateVisitAuthorityAdapter
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.contracts import DetectionObservation, EvidenceCandidate, FramePacket, TrackUpdate
from mockingbird.observation.frame_tracker import ProviderNeutralFrameTracker, TrackerConfiguration
from mockingbird.observation.visit_episode_assembler import assemble_visit_episodes, build_tracklets
from mockingbird.repository.product_repository import ObservationCandidateVisitModel, ProductRepository, VisitModel

STREAM_ID = "stream-backyard-feeder"
ZONE_ID = "zone-feeder"
BASE_TIME = datetime(2026, 9, 2, 7, 40, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"1" * 128 + b"\xff\xd9"

# v10 field-reported bbox centers (reproducer evidence only -- no code
# under test anywhere reads these numbers; see
# `test_persistent_confusor_pattern_is_rejected_at_an_arbitrary_location`
# and `test_weak_real_pattern_still_admits_at_the_former_confusor_location`
# for the adversarial checks proving this).
_TUBE_FEEDER_BOX = (0.448, 0.510, 0.488, 0.550)  # center ~= (0.468, 0.530)
_SAPLING_BOX = (0.830, 0.470, 0.870, 0.510)  # center ~= (0.85, 0.49) -- v10's weak-real-bird location
_LOCATION_A_BOX = (0.16, 0.66, 0.24, 0.74)  # v8/v9's own foliage-cluster location, reused unmodified


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _tracker_config(**overrides: object) -> TrackerConfiguration:
    """Mirrors the real deployed `frame_driven_provider.FrameDrivenSettings`
    defaults exactly -- identical to `test_hard_negative_visit_admission_
    precision_v1.py`'s own `_tracker_config`, duplicated (not imported) to
    keep this file self-contained, matching this codebase's own per-
    milestone test-file convention."""
    values: dict[str, object] = dict(
        strong_detection_threshold=0.70,
        minimum_detector_confirmations=2,
        minimum_tracker_support_frames=1,
        maximum_missed_frames=3,
        maximum_frame_gap_ms=1500,
        tracker_expiry_ms=1200,
        maximum_track_duration_ms=30_000,
        maximum_active_tracks=24,
        minimum_iou=0.05,
        maximum_centroid_distance=0.22,
        ambiguity_margin=0.01,
        maximum_unsupported_detector_ms=5000,
        negative_detector_frames_to_end=2,
        ambiguous_reentry_window_ms=1500,
        weak_detector_support_floor=0.05,
        maximum_weak_support_span_ms=15_000,
    )
    values.update(overrides)
    return TrackerConfiguration(**values)


def _tracker() -> ProviderNeutralFrameTracker:
    return ProviderNeutralFrameTracker(
        STREAM_ID, _tracker_config(), support_resolver=lambda _frame, track: track.bounding_box,
    )


def _frame(offset_ms: int) -> FramePacket:
    return FramePacket(
        stream_id=STREAM_ID, media_asset_id=f"repro:{offset_ms}",
        captured_at=BASE_TIME + timedelta(milliseconds=offset_ms),
        frame_id=f"repro-frame-{offset_ms}", source_offset_ms=offset_ms, width=1920, height=1080,
    )


def _detection(frame: FramePacket, box: tuple[float, float, float, float], *, confidence: float) -> DetectionObservation:
    return DetectionObservation(
        detector_id="onnx-cuda", label="animal", confidence=confidence, captured_at=frame.captured_at,
        observation_id=f"obs:{frame.frame_id}", frame_id=frame.frame_id, provider_id="frame-driven-onnx-cuda",
        model_key="md-v5a", bounding_box=box, class_source_label="animal", is_animal=True,
    )


def _drive(
    tracker: ProviderNeutralFrameTracker,
    ticks: list[tuple[int, tuple[float, tuple[float, float, float, float]] | None]],
) -> list[TrackUpdate]:
    updates: list[TrackUpdate] = []
    for offset_ms, payload in ticks:
        frame = _frame(offset_ms)
        detections = () if payload is None else (_detection(frame, payload[1], confidence=payload[0]),)
        updates.extend(tracker.observe(frame, detections).updates)
    return updates


def _finalize(tracker: ProviderNeutralFrameTracker) -> list[TrackUpdate]:
    return list(tracker.finalize("end_of_replay").updates)


def _evidence_candidates_for(generation_id: str, box: tuple[float, float, float, float]) -> tuple[EvidenceCandidate, ...]:
    return (
        EvidenceCandidate(
            media_asset_id=f"shadow-burst:{generation_id}-id", stream_id=STREAM_ID, role="high_resolution_burst",
            captured_at=BASE_TIME, frame_id=f"{generation_id}-frame-1", source_offset_ms=0, width=1920, height=1080,
            subject_geometry=box, track_generation_id=generation_id,
            quality_facts=(("decodable", True), ("temporal_alignment", "aligned"), ("track_supported", True)),
        ),
        EvidenceCandidate(
            media_asset_id=f"shadow-burst:{generation_id}-ctx", stream_id=STREAM_ID, role="context",
            captured_at=BASE_TIME, frame_id=f"{generation_id}-frame-2", source_offset_ms=0, width=1920, height=1080,
            subject_geometry=box, track_generation_id=generation_id,
            quality_facts=(("decodable", True), ("temporal_alignment", "aligned"), ("track_supported", True)),
        ),
    )


def _adapter(repository: ProductRepository) -> CandidateVisitAuthorityAdapter:
    return CandidateVisitAuthorityAdapter(
        repository, detector_provenance="onnx-cuda", tracker_provenance="frame-driven-onnx-cuda-v1",
        provider_key="frame-driven-onnx-cuda",
    )


def _activate(repository: ProductRepository, *, now: datetime = BASE_TIME) -> None:
    repository.set_observation_authority_mode(ObservationAuthorityMode.candidate_visit, stream_id=STREAM_ID, now=now)


def _build_tracklets(updates: list[TrackUpdate], *, box_by_generation: dict[str, tuple[float, float, float, float]]) -> tuple:
    generation_ids = {update.generation_id for update in updates}
    return build_tracklets(
        tuple(updates), stream_id=STREAM_ID,
        zone_id_by_generation={generation_id: ZONE_ID for generation_id in generation_ids},
        evidence_candidate_ids_by_generation={
            generation_id: tuple(
                candidate.media_asset_id
                for candidate in _evidence_candidates_for(generation_id, box_by_generation[generation_id])
            )
            for generation_id in generation_ids
        },
    )


def _assemble_one_proposal(updates: list[TrackUpdate], *, box: tuple[float, float, float, float]):
    generation_ids = {update.generation_id for update in updates}
    tracklets = _build_tracklets(updates, box_by_generation={generation_id: box for generation_id in generation_ids})
    result = assemble_visit_episodes(tracklets)
    assert len(result.proposals) == 1, "reproducer must assemble into exactly one chained proposal"
    return result.proposals[0]


def _attempt(repository: ProductRepository, proposal, *, box: tuple[float, float, float, float], observed_at: datetime = BASE_TIME):
    # Activation boundary is always set at `BASE_TIME` (the earliest
    # moment any reproducer here ever uses), regardless of how much later
    # `observed_at` is for a given attempt -- mirrors `test_hard_negative_
    # visit_admission_precision_v1.py`'s own `_activate` convention
    # exactly; safe to call repeatedly across sequential attempts on the
    # same repository (idempotent re-activation), unlike the per-Stream
    # accumulated scene-confusor region history this file's own
    # `TestSceneConfusorComposition` deliberately exercises across
    # multiple `_attempt` calls.
    _activate(repository)
    candidates = tuple(
        candidate
        for generation_id in proposal.constituent_generation_ids
        for candidate in _evidence_candidates_for(generation_id, box)
    )
    evidence_bytes = {candidate.media_asset_id: JPEG_BYTES for candidate in candidates}
    return _adapter(repository).attempt_candidate(
        proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=observed_at,
    )


# ---------------------------------------------------------------------------
# Construction helpers for the v10-shaped persistent-confusor chain: one
# generation dominates via its own extended natural persistence (never
# strong, never two consecutive genuine detections), optionally chained
# with further bare-minimum-confirmed filler generations -- the exact
# mechanism the v10 report traces ("accumulating enough individually-
# insufficient low-confidence detections within one continuation window to
# clear 2 * constituent_generation_count + 1 without ever reaching a strong
# detection").
# ---------------------------------------------------------------------------

_DOMINANT_CONFIDENCES = [0.15, 0.20, 0.18, 0.22, 0.16, 0.25, 0.19, 0.21, 0.17, 0.23, 0.20, 0.18, 0.24, 0.16, 0.19]


def _dominant_generation_ticks(start_ms: int, count: int, box: tuple[float, float, float, float]) -> tuple[list, int]:
    """`count` non-consecutive genuine detections (alternating detect/miss
    every 250ms, so `max_consecutive_detector_confirmed_frames` stays 1),
    all well below `strong_detection_threshold`, "confidence fluctuating
    noisily ... no directional trend" per the v10 report's own language --
    followed by a forced >5000ms gap so the generation terminates via
    `maximum_unsupported_duration` (one of the three real terminal reasons
    the accepted predecessor's own report already names for this exact
    static-confusor shape). Returns `(ticks, next_free_offset_ms)`."""
    assert count <= len(_DOMINANT_CONFIDENCES)
    ticks: list = []
    offset = start_ms
    for confidence in _DOMINANT_CONFIDENCES[:count]:
        ticks.append((offset, (confidence, box)))
        offset += 250
        ticks.append((offset, None))
        offset += 250
    ticks.append((offset + 5500, None))
    return ticks, offset + 5500 + 1000


def _filler_generation_ticks(start_ms: int, index: int, box: tuple[float, float, float, float]) -> tuple[list, int]:
    """One further independently-restarted generation confirmed on exactly
    the tracker's own bare 2-detection floor -- the identical shape
    `test_hard_negative_visit_admission_precision_v1.py`'s own Hard-
    negative C (`candidate-027`-shaped) reproducer already uses, chained
    within `merge_gap_ms` (15s) of the previous generation's end."""
    pair = (0.15 + 0.01 * index, 0.18 + 0.01 * index)
    ticks = [
        (start_ms, (pair[0], box)), (start_ms + 250, None), (start_ms + 500, (pair[1], box)),
        (start_ms + 500 + 5500, None),
    ]
    return ticks, start_ms + 500 + 5500 + 1000


def _persistent_confusor_chain(
    tracker: ProviderNeutralFrameTracker, box: tuple[float, float, float, float],
    *, dominant_count: int, filler_generations: int, start_ms: int = 0,
) -> list[TrackUpdate]:
    updates: list[TrackUpdate] = []
    dominant_ticks, offset = _dominant_generation_ticks(start_ms, dominant_count, box)
    updates += _drive(tracker, dominant_ticks)
    for index in range(filler_generations):
        filler_ticks, offset = _filler_generation_ticks(offset, index, box)
        updates += _drive(tracker, filler_ticks)
    return updates


# ---------------------------------------------------------------------------
# Persistent confusor -- the v10 escape itself. Pre-fix admits; post-fix
# rejects.
# ---------------------------------------------------------------------------


class TestPersistentConfusorRejected:
    def test_dominant_generation_plus_bare_minimum_filler_is_rejected(self, repository: ProductRepository) -> None:
        """The exact mechanism v10's own report traces: one generation
        (12 non-consecutive, never-strong detections -- comfortably inside
        the report's own disclosed 9-33 range) accumulates far more than
        the tracker's own bare confirmation floor via its own natural
        persistence, chained with 3 further bare-minimum-confirmed
        restarts (18 total detections, 4 constituent generations). This
        clears the pre-existing `2 * constituent_generation_count + 1`
        floor (18 > 9) -- reproducing the actual pre-fix admission -- but
        removing the single dominant generation leaves only 6 detections
        across the 3 remaining generations, which does not clear *their*
        own identically-scaled floor (6 <= 7), so the new check correctly
        identifies the credit as concentrated in one generation rather
        than genuinely distributed across the chain."""
        tracker = _tracker()
        updates = _persistent_confusor_chain(tracker, _TUBE_FEEDER_BOX, dominant_count=12, filler_generations=3)
        proposal = _assemble_one_proposal(updates, box=_TUBE_FEEDER_BOX)

        assert len(proposal.constituent_generation_ids) == 4
        assert proposal.confidence_evidence.detection_count == 18
        assert proposal.confidence_evidence.strong_detection_count == 0
        assert proposal.confidence_evidence.max_consecutive_detector_confirmed_frames == 1
        assert proposal.confidence_evidence.max_single_generation_detection_count == 12
        # Pre-fix diagnostic fact, asserted directly (not merely narrated):
        # the OLD rule's own floor is cleared by the raw total alone.
        old_floor = 2 * len(proposal.constituent_generation_ids) + 1
        assert proposal.confidence_evidence.detection_count > old_floor, "must reproduce the actual pre-fix escape"

        outcome = _attempt(repository, proposal, box=_TUBE_FEEDER_BOX)
        assert not outcome.created
        assert outcome.outcome == "reject_insufficient_detector_corroboration"
        assert outcome.reason == "corroboration_concentrated_in_single_generation"
        with repository.session_factory() as session:
            assert session.get(ObservationCandidateVisitModel, proposal.proposal_id) is None

    def test_padding_the_chain_with_more_filler_generations_does_not_rescue_it(
        self, repository: ProductRepository,
    ) -> None:
        """Adversarial: chaining gaming (this milestone's own required
        self-review). Adding two more bare-minimum filler generations to
        the reproducer above raises both the raw total (22) and the old
        floor (13) -- still clears the old floor -- but the remaining
        generations' own floor grows right alongside them (2*5+1=11 vs.
        a remainder of 10), so the padding does not manufacture
        admission. Proves the fix is not merely a repackaged, gameable
        raw-count comparison."""
        tracker = _tracker()
        updates = _persistent_confusor_chain(tracker, _TUBE_FEEDER_BOX, dominant_count=12, filler_generations=5)
        proposal = _assemble_one_proposal(updates, box=_TUBE_FEEDER_BOX)
        assert len(proposal.constituent_generation_ids) == 6
        assert proposal.confidence_evidence.detection_count == 22
        assert proposal.confidence_evidence.detection_count > 2 * 6 + 1

        outcome = _attempt(repository, proposal, box=_TUBE_FEEDER_BOX)
        assert not outcome.created
        assert outcome.outcome == "reject_insufficient_detector_corroboration"

    def test_persistent_confusor_pattern_is_rejected_at_an_arbitrary_location(
        self, repository: ProductRepository,
    ) -> None:
        """Adversarial self-review: the identical dominant-generation
        signature at a bounding box nothing like the real v10 tube-feeder
        location proves this is a semantic corroboration-structure rule,
        never scene-coordinate memorization (mirrors `test_hard_negative_
        visit_admission_precision_v1.py`'s own identical-in-spirit check
        for the predecessor rule)."""
        arbitrary_box = (0.02, 0.90, 0.08, 0.96)
        tracker = _tracker()
        updates = _persistent_confusor_chain(tracker, arbitrary_box, dominant_count=13, filler_generations=3)
        proposal = _assemble_one_proposal(updates, box=arbitrary_box)
        outcome = _attempt(repository, proposal, box=arbitrary_box)
        assert not outcome.created
        assert outcome.outcome == "reject_insufficient_detector_corroboration"


# ---------------------------------------------------------------------------
# Previously-rejected hard negatives -- must remain rejected (regression
# check against the accepted predecessor's own field-derived signatures).
# ---------------------------------------------------------------------------


class TestPreviousHardNegativesRemainRejected:
    def test_v8_location_a_foliage_bare_minimum_chain_still_rejected(self, repository: ProductRepository) -> None:
        """v8/v9's own recurring foliage-cluster location, exactly re-
        confirmed a third time in v10's own session (offset 3,201,232-
        3,209,645ms, `detection_count == 3` at the N=1 scaled floor,
        `terminal_reason: maximum_unsupported_duration`) -- single
        generation, completely unaffected by this milestone's new N>=2
        concentration check (nothing to recurse against at N=1)."""
        tracker = _tracker()
        updates = _drive(tracker, [
            (0, (0.15, _LOCATION_A_BOX)), (250, None), (500, (0.18, _LOCATION_A_BOX)),
        ])
        updates += _drive(tracker, [(6500, None)])
        proposal = _assemble_one_proposal(updates, box=_LOCATION_A_BOX)
        assert len(proposal.constituent_generation_ids) == 1
        outcome = _attempt(repository, proposal, box=_LOCATION_A_BOX)
        assert not outcome.created
        assert outcome.outcome == "reject_insufficient_detector_corroboration"
        assert outcome.reason == "never_strong_and_minimal_detector_corroboration"

    def test_tracker_only_chained_bare_minimum_false_chain_still_rejected(self, repository: ProductRepository) -> None:
        """v9's own `visit-observation-candidate-027`-shaped chain (4
        independently-restarted generations, each confirmed on exactly the
        bare 2-detection floor, summed `detection_count == 8` against a
        floor of 9) -- already correctly rejected by the predecessor rule
        via the *original* floor check alone (8 <= 9); this milestone's
        new concentration check is not even reached (short-circuited),
        confirming zero behavioral change for this already-accepted case."""
        tracker = _tracker()
        updates: list[TrackUpdate] = []
        offset = 0
        for index, confidence_pair in enumerate(((0.15, 0.18), (0.20, 0.16), (0.25, 0.19), (0.30, 0.22))):
            filler_ticks, offset = _filler_generation_ticks(offset, index, _TUBE_FEEDER_BOX)
            # Reuse the exact real confidence pair per restart, not the
            # helper's own synthetic index-based one, to match v9's own
            # reported 0.147-0.363 range precisely.
            updates += _drive(tracker, [
                (filler_ticks[0][0], (confidence_pair[0], _TUBE_FEEDER_BOX)),
                (filler_ticks[1][0], None),
                (filler_ticks[2][0], (confidence_pair[1], _TUBE_FEEDER_BOX)),
                (filler_ticks[3][0], None),
            ])
        proposal = _assemble_one_proposal(updates, box=_TUBE_FEEDER_BOX)
        assert len(proposal.constituent_generation_ids) == 4
        assert proposal.confidence_evidence.detection_count == 8
        outcome = _attempt(repository, proposal, box=_TUBE_FEEDER_BOX)
        assert not outcome.created
        assert outcome.outcome == "reject_insufficient_detector_corroboration"


# ---------------------------------------------------------------------------
# Weak-real bird -- v10's own field-confirmed positive control. Must
# remain admitted (single generation; this milestone's own fix does not
# touch this case at all).
# ---------------------------------------------------------------------------


class TestWeakRealBirdAdmitted:
    def test_v10_small_distant_bird_signature_is_admitted(self, repository: ProductRepository) -> None:
        """v10's own real, disclosed signature for candidates 003/004/006
        (a small, pale, distant bird matching `northern_mockingbird`,
        perched on a sparse sapling): never reached `strong_detection_
        count > 0` (max confidence 0.384/0.265/0.248), admitted "purely
        via count-based corroboration" with 13-18 detections per proposal
        -- reproduced here at 14, the midpoint of that disclosed range, in
        a single generation (matching the field description of one
        continuous, if weak, presence). This is the exact real case this
        milestone's own governing brief requires be retained; the fix's
        new concentration check does not apply at N=1 (see the module
        docstring's own mathematical derivation for why no count-magnitude
        rule safely could)."""
        confidences = [0.22, 0.28, 0.24, 0.31, 0.26, 0.29, 0.23, 0.27, 0.25, 0.30, 0.24, 0.28, 0.26, 0.29]
        assert len(confidences) == 14
        tracker = _tracker()
        ticks: list = []
        offset = 0
        for confidence in confidences:
            ticks.append((offset, (confidence, _SAPLING_BOX)))
            offset += 250
            ticks.append((offset, None))
            offset += 250
        updates = _drive(tracker, ticks)
        updates += _finalize(tracker)
        proposal = _assemble_one_proposal(updates, box=_SAPLING_BOX)
        assert len(proposal.constituent_generation_ids) == 1
        assert proposal.confidence_evidence.detection_count == 14
        assert proposal.confidence_evidence.strong_detection_count == 0
        outcome = _attempt(repository, proposal, box=_SAPLING_BOX)
        assert outcome.created
        assert outcome.outcome == "created"

    def test_weak_real_pattern_still_admits_at_the_former_confusor_location(self, repository: ProductRepository) -> None:
        """Adversarial self-review, the other required direction (this
        milestone's own explicit instruction): the identical weak-real-
        bird signature above, moved onto the persistent confusor's own
        real bbox, still admits -- directly disproving a hidden spatial
        blacklist. If its evidence is genuinely as strong/independent as
        the sapling case, location must not matter either way."""
        confidences = [0.22, 0.28, 0.24, 0.31, 0.26, 0.29, 0.23, 0.27, 0.25, 0.30, 0.24, 0.28, 0.26, 0.29]
        tracker = _tracker()
        ticks: list = []
        offset = 0
        for confidence in confidences:
            ticks.append((offset, (confidence, _TUBE_FEEDER_BOX)))
            offset += 250
            ticks.append((offset, None))
            offset += 250
        updates = _drive(tracker, ticks)
        updates += _finalize(tracker)
        proposal = _assemble_one_proposal(updates, box=_TUBE_FEEDER_BOX)
        outcome = _attempt(repository, proposal, box=_TUBE_FEEDER_BOX)
        assert outcome.created


# ---------------------------------------------------------------------------
# Stationary real bird -- mandatory control (this milestone's own explicit
# requirement): a real bird with little geometry variation must not be
# rejected merely for being static. Multi-generation (re-acquired after a
# brief loss) with evenly-distributed, not concentrated, corroboration.
# ---------------------------------------------------------------------------


class TestStationaryRealBirdAdmitted:
    def test_stationary_bird_with_balanced_multi_generation_corroboration_is_admitted(
        self, repository: ProductRepository,
    ) -> None:
        """A genuinely perched, motionless real bird (every detection at
        the *exact* same bounding box -- geometry plays no role in this
        check at all, proving the point directly rather than merely by
        omission) whose detector confirmation is briefly interrupted twice
        (a lighting flicker, a leaf swaying across it) and reacquired --
        two constituent generations, each contributing an equal, moderate
        5 detections (10 total, comfortably above both the old floor
        (2*2+1=5) and, critically, this milestone's new check: removing
        either generation leaves 5 detections against the *other*
        generation's own scaled floor (2*1+1=3), which still clears)."""
        box = (0.60, 0.20, 0.66, 0.28)
        tracker = _tracker()
        updates: list[TrackUpdate] = []
        offset = 0
        for _generation_index in range(2):
            ticks: list = []
            for confidence in (0.30, 0.29, 0.32, 0.31, 0.28):
                ticks.append((offset, (confidence, box)))
                offset += 250
                ticks.append((offset, None))
                offset += 250
            updates += _drive(tracker, ticks)
            updates += _drive(tracker, [(offset + 5500, None)])
            offset += 5500 + 1000
        proposal = _assemble_one_proposal(updates, box=box)
        assert len(proposal.constituent_generation_ids) == 2
        assert proposal.confidence_evidence.detection_count == 10
        assert proposal.confidence_evidence.max_single_generation_detection_count == 5

        outcome = _attempt(repository, proposal, box=box)
        assert outcome.created
        assert outcome.outcome == "created"


# ---------------------------------------------------------------------------
# Brief real bird -- mandatory control: a short encounter with limited
# detector opportunities must not require a long observation period.
# ---------------------------------------------------------------------------


class TestBriefRealBirdAdmitted:
    def test_brief_landing_and_departure_is_admitted(self, repository: ProductRepository) -> None:
        """Present only briefly, but genuinely present -- a real back-to-
        back consecutive pair while it is actually there admits via the
        completely untouched streak axis, independent of the count axis
        this milestone changes at all."""
        box = (0.55, 0.40, 0.62, 0.50)
        tracker = _tracker()
        updates = _drive(tracker, [(0, (0.35, box)), (250, (0.40, box)), (500, (0.33, box))])
        updates += _finalize(tracker)
        proposal = _assemble_one_proposal(updates, box=box)
        assert len(proposal.constituent_generation_ids) == 1
        outcome = _attempt(repository, proposal, box=box)
        assert outcome.created


# ---------------------------------------------------------------------------
# Intermittent real bird -- mandatory control: detector loses and
# re-acquires it; a credible Visit must survive. Multi-generation, evenly
# distributed corroboration at a higher generation count than the
# stationary control above.
# ---------------------------------------------------------------------------


class TestIntermittentRealBirdAdmitted:
    def test_bird_lost_and_reacquired_twice_with_balanced_corroboration_survives(
        self, repository: ProductRepository,
    ) -> None:
        """Three independently-restarted generations (lost/reacquired
        twice), each contributing an equal 4 detections (12 total; old
        floor 2*3+1=7, cleared). Removing the single largest (any one of
        the three, tied at 4) leaves 8 detections across the remaining 2
        generations against their own scaled floor (2*2+1=5) -- still
        clears, so genuine, evenly-spread re-acquisition is not penalized
        the way one generation's own extended coasting is."""
        box = (0.12, 0.45, 0.18, 0.53)
        tracker = _tracker()
        updates: list[TrackUpdate] = []
        offset = 0
        for _generation_index in range(3):
            ticks: list = []
            for confidence in (0.20, 0.23, 0.19, 0.25):
                ticks.append((offset, (confidence, box)))
                offset += 250
                ticks.append((offset, None))
                offset += 250
            updates += _drive(tracker, ticks)
            updates += _drive(tracker, [(offset + 5500, None)])
            offset += 5500 + 1000
        proposal = _assemble_one_proposal(updates, box=box)
        assert len(proposal.constituent_generation_ids) == 3
        assert proposal.confidence_evidence.detection_count == 12
        assert proposal.confidence_evidence.max_single_generation_detection_count == 4

        outcome = _attempt(repository, proposal, box=box)
        assert outcome.created
        assert outcome.outcome == "created"


# ---------------------------------------------------------------------------
# Strong positive -- unaffected.
# ---------------------------------------------------------------------------


class TestStrongPositiveUnaffected:
    def test_normal_confident_visit_is_admitted_unchanged(self, repository: ProductRepository) -> None:
        box = (0.40, 0.40, 0.50, 0.50)
        tracker = _tracker()
        updates = _drive(tracker, [(0, (0.87, box)), (250, (0.91, box))])
        updates += _finalize(tracker)
        proposal = _assemble_one_proposal(updates, box=box)
        outcome = _attempt(repository, proposal, box=box)
        assert outcome.created
        assert outcome.outcome == "created"


# ---------------------------------------------------------------------------
# Known residual, honestly disclosed (not hidden): two independently-
# substantial generations, neither individually dominant, are not
# rejected by this check. This is a deliberate, documented judgment call,
# not an oversight -- see the module docstring / this milestone's report.
# ---------------------------------------------------------------------------


class TestDisclosedResidual:
    def test_two_equally_substantial_generations_are_not_flagged_as_concentrated(
        self, repository: ProductRepository,
    ) -> None:
        """Two generations, each independently contributing 15 detections
        (30 total; old floor 2*2+1=5, cleared). Removing either leaves 15
        against the other's own scaled floor (2*1+1=3) -- clears easily,
        so this shape admits. Documented, not silently accepted: two
        genuinely separate, independently-substantial re-acquisitions is
        judged different in kind from one generation coasting alongside
        bare-minimum filler, but this reproducer exists so the boundary is
        explicit and tested, not merely asserted in prose."""
        box = (0.75, 0.75, 0.81, 0.81)
        tracker = _tracker()
        updates: list[TrackUpdate] = []
        offset = 0
        for _generation_index in range(2):
            ticks: list = []
            for confidence in _DOMINANT_CONFIDENCES[:15]:
                ticks.append((offset, (confidence, box)))
                offset += 250
                ticks.append((offset, None))
                offset += 250
            updates += _drive(tracker, ticks)
            updates += _drive(tracker, [(offset + 5500, None)])
            offset += 5500 + 1000
        proposal = _assemble_one_proposal(updates, box=box)
        assert len(proposal.constituent_generation_ids) == 2
        assert proposal.confidence_evidence.detection_count == 30
        assert proposal.confidence_evidence.max_single_generation_detection_count == 15

        outcome = _attempt(repository, proposal, box=box)
        assert outcome.created  # disclosed residual, not a defect -- see report


# ---------------------------------------------------------------------------
# Multi-subject safety -- no cross-subject corroboration, and the new
# per-proposal field must never mix subjects.
# ---------------------------------------------------------------------------


class TestMultiSubjectSafety:
    def test_weak_real_sibling_is_not_killed_by_a_strong_simultaneous_sibling(
        self, repository: ProductRepository,
    ) -> None:
        strong_box = (0.05, 0.05, 0.15, 0.15)
        weak_box = (0.80, 0.80, 0.86, 0.86)
        tracker = _tracker()
        updates: list[TrackUpdate] = []
        for offset_ms, strong_conf, weak_conf in (
            (0, 0.88, 0.22), (250, None, None), (500, 0.90, 0.27),
            (750, None, None), (1000, None, 0.24), (1250, None, None), (1500, None, 0.29),
        ):
            frame = _frame(offset_ms)
            detections = tuple(
                d for d in (
                    _detection(frame, strong_box, confidence=strong_conf) if strong_conf is not None else None,
                    _detection(frame, weak_box, confidence=weak_conf) if weak_conf is not None else None,
                )
                if d is not None
            )
            updates.extend(tracker.observe(frame, detections).updates)
        updates += _finalize(tracker)

        box_by_generation = {u.generation_id: (strong_box if u.bounding_box == strong_box else weak_box) for u in updates}
        tracklets = _build_tracklets(updates, box_by_generation=box_by_generation)
        assert len(tracklets) == 2
        result = assemble_visit_episodes(tracklets)
        assert len(result.proposals) == 2

        _activate(repository)
        adapter = _adapter(repository)
        created = 0
        for proposal in result.proposals:
            generation_id = proposal.constituent_generation_ids[0]
            tracklet = next(t for t in tracklets if t.generation_id == generation_id)
            candidates = _evidence_candidates_for(generation_id, tracklet.geometry_envelope)
            evidence_bytes = {candidate.media_asset_id: JPEG_BYTES for candidate in candidates}
            outcome = adapter.attempt_candidate(
                proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=BASE_TIME,
            )
            assert outcome.created
            created += 1
        assert created == 2
        weak_proposal = next(p for p in result.proposals if p.confidence_evidence.strong_detection_count == 0)
        assert weak_proposal.confidence_evidence.detection_count == 4
        assert weak_proposal.confidence_evidence.max_single_generation_detection_count == 4


# ---------------------------------------------------------------------------
# Unknown evidence -- a legacy summary that predates this milestone's new
# field must not be falsely rejected.
# ---------------------------------------------------------------------------


class TestUnknownEvidenceDoesNotFalselyReject:
    def test_missing_max_single_generation_detection_count_falls_back_to_pre_existing_behavior(self) -> None:
        """Direct unit check on the pure gate function (no repository
        needed): a duck-typed `confidence_evidence` object exposing every
        pre-existing field but *not* `max_single_generation_detection_
        count` (a legacy record, or a caller that predates this
        milestone) is judged exactly as the pre-existing rule would have --
        the new concentration check degrades to "not concentrated," never
        a guessed reject, matching this codebase's universal unknown-
        evidence convention."""
        from mockingbird.observation import candidate_quality_gate as gate

        class _LegacyEvidence:
            detection_count = 18
            strong_detection_count = 0
            max_consecutive_detector_confirmed_frames = 1
            # deliberately no `max_single_generation_detection_count` attribute

        reason = gate._insufficient_detector_corroboration(_LegacyEvidence(), constituent_generation_count=4)
        assert reason is None, "unknown concentration fact must never manufacture a reject"


# ---------------------------------------------------------------------------
# Species-escalation trace -- rejected persistent confusor cannot reach
# species inference.
# ---------------------------------------------------------------------------


class TestSpeciesEscalation:
    def test_rejected_persistent_confusor_never_becomes_a_visit_species_inference_could_reach(
        self, repository: ProductRepository,
    ) -> None:
        tracker = _tracker()
        updates = _persistent_confusor_chain(tracker, _TUBE_FEEDER_BOX, dominant_count=12, filler_generations=3)
        proposal = _assemble_one_proposal(updates, box=_TUBE_FEEDER_BOX)
        outcome = _attempt(repository, proposal, box=_TUBE_FEEDER_BOX)
        assert not outcome.created
        assert outcome.visit_id is None
        assert outcome.event_id is None
        with repository.session_factory() as session:
            assert session.get(ObservationCandidateVisitModel, proposal.proposal_id) is None
            with pytest.raises(ValueError, match="missing_visit"):
                repository._review_identification_item_for_visit(session, "visit-observation-candidate-nonexistent")


# ---------------------------------------------------------------------------
# Reviewed-truth safety.
# ---------------------------------------------------------------------------


class TestReviewedTruthPreserved:
    def test_unrelated_persistent_confusor_rejection_does_not_disturb_a_reviewed_visit(
        self, repository: ProductRepository,
    ) -> None:
        strong_box = (0.40, 0.40, 0.50, 0.50)
        tracker = _tracker()
        strong_updates = _drive(tracker, [(0, (0.90, strong_box)), (250, (0.92, strong_box))])
        strong_updates += _finalize(tracker)
        strong_proposal = _assemble_one_proposal(strong_updates, box=strong_box)
        strong_outcome = _attempt(repository, strong_proposal, box=strong_box)
        assert strong_outcome.created
        visit_id = strong_outcome.visit_id
        assert visit_id is not None

        from mockingbird.api.schemas import ReviewCorrectionCreate

        repository.create_review_label(
            ReviewCorrectionCreate(
                target_type="visit", target_id=visit_id, label="northern_cardinal",
                review_origin="human", reviewer_identity="reviewer@example.test",
            ),
            BASE_TIME + timedelta(minutes=1),
        )

        confusor_tracker = _tracker()
        confusor_updates = _persistent_confusor_chain(
            confusor_tracker, _TUBE_FEEDER_BOX, dominant_count=12, filler_generations=3, start_ms=20_000,
        )
        confusor_proposal = _assemble_one_proposal(confusor_updates, box=_TUBE_FEEDER_BOX)
        confusor_outcome = _attempt(repository, confusor_proposal, box=_TUBE_FEEDER_BOX)
        assert not confusor_outcome.created

        with repository.session_factory() as session:
            reviewed_visit = session.get(VisitModel, visit_id)
            assert reviewed_visit is not None
            assert reviewed_visit.review_status == "reviewed"
            assert reviewed_visit.reviewed_label == "northern_cardinal"


# ---------------------------------------------------------------------------
# Rate-limit interaction.
# ---------------------------------------------------------------------------


class TestRateLimitInteraction:
    def test_rejected_persistent_confusor_does_not_consume_candidate_rate_limit_capacity(
        self, repository: ProductRepository,
    ) -> None:
        _activate(repository)
        before = repository.get_observation_authority_state(stream_id=STREAM_ID)
        assert before.candidates_created_in_session == 0

        tracker = _tracker()
        updates = _persistent_confusor_chain(tracker, _TUBE_FEEDER_BOX, dominant_count=12, filler_generations=3)
        proposal = _assemble_one_proposal(updates, box=_TUBE_FEEDER_BOX)
        outcome = _attempt(repository, proposal, box=_TUBE_FEEDER_BOX)
        assert not outcome.created

        after = repository.get_observation_authority_state(stream_id=STREAM_ID)
        assert after.candidates_created_in_session == 0
        assert after.candidates_created_in_trailing_hour == 0
        assert after.candidates_created_count == 0
        assert after.candidates_attempted_count == 1


# ---------------------------------------------------------------------------
# V10-shaped scene-confusor composition: drives four sequential, single-
# generation, never-strong proposals at the *same* real bbox through the
# real, unmodified, already-live `ProductRepository.create_candidate_
# visit_from_proposal` (which already includes the scene-confusor check
# unconditionally, since schema 34 -- see docs/independent-corroboration-
# value-persistent-confusor-admission-correctness-v1-report.md
# "Scene-confusor composition"). This is the empirical answer to this
# milestone's own required question: does an *already-live*, *unmodified*
# generalized mechanism already catch the repeat-occurrence dimension this
# milestone's own new corroboration check (by design, at N=1) cannot?
# ---------------------------------------------------------------------------


class TestSceneConfusorComposition:
    def test_repeated_single_generation_never_strong_occurrences_compose_with_scene_confusor(
        self, repository: ProductRepository,
    ) -> None:
        """Four single-generation (N=1, this milestone's own fix
        deliberately inert here) proposals at the same real bbox, each
        never strong, spaced minutes apart within one session -- exactly
        v10's own reported candidates-005/007/008/009 shape (each
        individually indistinguishable from a genuine weak bird by
        corroboration structure alone). Records, per attempt, which gate
        (this milestone's quality-gate check, or the pre-existing,
        unmodified scene-confusor check) actually decided the outcome --
        the report's own "Scene-confusor composition" section states the
        exact result plainly rather than asserting a specific occurrence
        index here, since the real answer is load-bearing evidence, not
        an assumption to bake into the test."""
        # Realistic per-occurrence jitter: each of the four separate
        # admitted-shaped proposals' own representative box drifts by
        # ~1-2px equivalent (~0.001 normalized) at 1920x1080, never
        # literal-float-identical across occurrences -- closer to what
        # four genuinely separate track generations at one real static
        # feature would actually each report than a toy constant box.
        # Confirmed directly (not assumed) not to change the result below
        # versus an exact-identical box.
        base = _TUBE_FEEDER_BOX
        jitters = [(0.0, 0.0), (0.0008, -0.0006), (-0.0005, 0.0009), (0.0011, 0.0003)]

        _activate(repository)
        outcomes = []
        for index in range(4):
            dx, dy = jitters[index]
            box = (base[0] + dx, base[1] + dy, base[2] + dx, base[3] + dy)
            # 9, 12, 15, 18 detections across the four attempts -- squarely
            # inside the v10 report's own disclosed 9-33 range for this
            # exact location, varied per attempt the way four genuinely
            # separate real occurrences would be.
            target_count = 9 + index * 3
            confidences = [_DOMINANT_CONFIDENCES[i % len(_DOMINANT_CONFIDENCES)] for i in range(target_count)]
            assert len(confidences) == target_count
            tracker = _tracker()
            ticks: list = []
            offset = index * 300_000  # minutes apart within one session, like the real cohort
            for confidence in confidences:
                ticks.append((offset, (confidence, box)))
                offset += 250
                ticks.append((offset, None))
                offset += 250
            updates = _drive(tracker, ticks)
            updates += _finalize(tracker)
            proposal = _assemble_one_proposal(updates, box=box)
            assert len(proposal.constituent_generation_ids) == 1
            outcome = _attempt(repository, proposal, box=box, observed_at=BASE_TIME + timedelta(milliseconds=index * 300_000))
            outcomes.append(outcome)

        # This milestone's own new corroboration check is provably inert
        # for every one of these (N=1 throughout, by construction) -- any
        # rejection observed here is therefore attributable only to the
        # pre-existing, unmodified scene-confusor mechanism, never to
        # this milestone's own change.
        assert all(
            outcome.outcome != "reject_insufficient_detector_corroboration" for outcome in outcomes
        ), "this milestone's own fix must stay inert at N=1, exactly as designed"
        # The empirically-observed composition result (see this
        # milestone's own report, "Scene-confusor composition," for the
        # full discussion, including the honest gap between this
        # controlled reproduction and the real v10 session, which never
        # recorded whether scene-confusor state was itself consulted):
        # the first three occurrences admit (the already-live mechanism's
        # own `min_occurrences_to_suspect` floor, 3, has not yet been
        # reached from *this Stream's own prior history*), and the fourth
        # is blocked by the pre-existing, completely unmodified scene-
        # confusor mechanism -- not by this milestone's own change.
        assert [outcome.outcome for outcome in outcomes] == [
            "created", "created", "created", "blocked_scene_confusor_suspected",
        ]
        assert outcomes[3].reason == "recurring_static_scene_geometry"
