"""Hard-Negative Visit Admission Precision & Species-Escalation Correctness v1.

Field-derived reproducers, driven through the real, unmodified production
path -- `ProviderNeutralFrameTracker.observe()` (genuine detector
observations, tracked exactly like a live Camera Node session) ->
`build_tracklets`/`assemble_visit_episodes` (unmodified) ->
`CandidateVisitAuthorityAdapter.attempt_candidate` -> a real, isolated
`ProductRepository` (unmodified except for the one new admission-time check
under test, `candidate_quality_gate.reject_insufficient_detector_
corroboration`) -- for:

- **Hard-negative A**: a recurring foliage/hanging-leaf-shaped location
  (Representative Daylight Gate A Field Acceptance v8/v9's own reported
  bbox center ~(0.20, 0.70)) -- weak, zero-strong, minimally corroborated.
- **Hard-negative B**: a feeder-cap sun-glint-shaped location (v9's own
  bbox center ~(0.467, 0.530), and `visit-observation-candidate-026`'s own
  real, traced signature: 3 raw detections, confidence 0.109-0.111, the one
  confirmed-false Visit that received a wrong confident species label).
- **Hard-negative C**: a tracker-only *chained* weak false chain (v9's own
  `visit-observation-candidate-027`: many short, independently-restarted
  track generations at one static location, none individually exceeding the
  tracker's own bare confirmation floor) -- the shape `contracts.merge_
  confidence_evidence`'s own max-not-sum `max_consecutive_detector_
  confirmed_frames` handling exists to keep ungameable.

Every required genuine-weak-bird positive control (small/distant, brief
landing/departure, low-confidence-but-real, partially occluded,
intermittently corroborated, multi-subject sibling, sustained activity) is
built the same way and asserted to still admit -- see
docs/hard-negative-visit-admission-precision-species-escalation-correctness-
v1-report.md for the full field-evidence trace and design rationale this
file exercises.
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

# Reuses the same demo-seeded Stream/Zone ids `tests/test_candidate_visit_
# adapter.py`'s own established convention does -- `ProductRepository.
# __init__` calls `seed_if_empty()` on a fresh database, which creates
# exactly these ids (`mockingbird.api.demo_data`); a real, valid `StreamModel`
# row is required for `create_candidate_visit_from_proposal` to reach the
# quality gate at all (`missing_stream` otherwise).
STREAM_ID = "stream-backyard-feeder"
ZONE_ID = "zone-feeder"
BASE_TIME = datetime(2026, 9, 1, 15, 0, 0, tzinfo=UTC)
JPEG_BYTES = b"\xff\xd8\xff\xe0" + b"1" * 128 + b"\xff\xd9"

# Location A (Representative Daylight Gate A Field Acceptance v8/v9's own
# reported "hanging leaf cluster / thin branch tip over the road" bbox
# center) and Location B (v9's own reported feeder-cap sun-glint bbox
# center) -- reproducer evidence, per this milestone's own explicit
# instruction, never the fix itself (no code anywhere reads these numbers;
# see `test_rejection_is_not_keyed_to_either_known_field_location` below for
# the adversarial check that this file's own logic is not overfit to them).
_LOCATION_A_BOX = (0.16, 0.66, 0.24, 0.74)
_LOCATION_B_BOX = (0.446, 0.517, 0.488, 0.543)


@pytest.fixture
def repository(tmp_path: Path) -> ProductRepository:
    repo = ProductRepository(db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}", media_root=tmp_path / "media")
    yield repo
    repo.close()


def _tracker_config(**overrides: object) -> TrackerConfiguration:
    """Mirrors `frame_driven_provider.FrameDrivenSettings`'s own deployed
    production defaults exactly (not `test_frame_tracker.py`'s own looser
    `_config()`), so every reproducer here exercises the tracker under the
    same bounds a real Camera Node session actually runs with."""
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
    # A maximally *generous* tracker-support resolver -- always successfully
    # re-confirms a track at its own last-known box on a miss, the same
    # stand-in `test_frame_tracker.py::test_ghost_tracker_support_does_not_
    # absorb_a_later_distinct_appearance` already uses. Deliberately chosen
    # so every reproducer below gives the tracker every benefit of the
    # doubt to persist a weak signal via patch-matching -- if the new
    # admission check still correctly rejects a hard negative *despite* the
    # tracker doing everything it can to keep it alive, that is the
    # strongest possible proof this is an admission-contract fix, not an
    # accidental tracking-layer side effect.
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
    """`ticks`: `(offset_ms, None)` for a genuine detector miss this
    analysis frame, or `(offset_ms, (confidence, box))` for a genuine
    matched detection. Every tick is a real `tracker.observe()` call --
    nothing here fabricates a `TrackUpdate` directly."""
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
    """`build_tracklets`, with every generation's own `evidence_candidate_ids`
    populated (via `_evidence_candidates_for`) so the resulting proposal's
    `evidence_media_asset_ids` union is non-empty -- otherwise `evidence_
    scoring.score_proposal_evidence` has nothing to select from regardless
    of what the caller later supplies as `media`, and every proposal here
    would fail closed with `blocked_missing_evidence` before the check
    under test is ever reached."""
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


def _attempt_all_proposals(repository: ProductRepository, updates: list[TrackUpdate], *, box: tuple[float, float, float, float]):
    """Real pipeline tail: `build_tracklets` -> `assemble_visit_episodes` ->
    one `attempt_candidate` call per resulting proposal (every reproducer
    here uses one fixed location, so every constituent generation shares
    `box`). Returns `(proposals, outcomes)` in the same order."""
    generation_ids = {update.generation_id for update in updates}
    tracklets = _build_tracklets(updates, box_by_generation={generation_id: box for generation_id in generation_ids})
    assert tracklets, "reproducer must yield at least one confirmed tracklet"
    result = assemble_visit_episodes(tracklets)
    _activate(repository)
    adapter = _adapter(repository)
    outcomes = []
    for proposal in result.proposals:
        candidates = tuple(
            candidate
            for generation_id in proposal.constituent_generation_ids
            for candidate in _evidence_candidates_for(generation_id, box)
        )
        evidence_bytes = {candidate.media_asset_id: JPEG_BYTES for candidate in candidates}
        outcomes.append(
            adapter.attempt_candidate(proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=BASE_TIME),
        )
    return result.proposals, outcomes


# --------------------------------------------------------------------------
# Hard negatives -- must be rejected, no user-visible Visit created.
# --------------------------------------------------------------------------


class TestHardNegativesRejected:
    def test_location_a_recurring_foliage_like_chain_is_rejected(self, repository: ProductRepository) -> None:
        """Hard-negative A: a static, weak, zero-strong location confirmed
        on exactly the tracker's own bare 2-detection floor, the two
        detections non-consecutive (a genuine miss between them) -- matches
        v8/v9's own reported signature for this recurring location: no
        individual Visit's real corroboration count was ever reported above
        this floor at Location A."""
        tracker = _tracker()
        updates = _drive(tracker, [
            (0, (0.15, _LOCATION_A_BOX)),
            (250, None),
            (500, (0.18, _LOCATION_A_BOX)),
        ])
        updates += _drive(tracker, [(6500, None)])  # >5000ms since last genuine detection -> maximum_unsupported_duration
        proposals, outcomes = _attempt_all_proposals(repository, updates, box=_LOCATION_A_BOX)
        assert len(outcomes) == 1
        assert not outcomes[0].created
        assert outcomes[0].outcome == "reject_insufficient_detector_corroboration"
        with repository.session_factory() as session:
            assert session.get(ObservationCandidateVisitModel, proposals[0].proposal_id) is None

    def test_location_b_glint_static_object_chain_is_rejected(self, repository: ProductRepository) -> None:
        """Hard-negative B: `visit-observation-candidate-026`'s own real,
        traced signature -- exactly 3 genuine detections, confidence
        0.109-0.111 (this milestone's report cites the exact figures),
        never consecutive, at the feeder-cap sun-glint location. This is
        the one v9 confirmed-false Visit that received a confident wrong
        species label; see `TestSpeciesEscalation` below for the direct
        consequence of this rejection on that question."""
        tracker = _tracker()
        updates = _drive(tracker, [
            (0, (0.109, _LOCATION_B_BOX)),
            (250, None),
            (500, (0.111, _LOCATION_B_BOX)),
            (750, None),
            (1000, (0.110, _LOCATION_B_BOX)),
        ])
        updates += _drive(tracker, [(6500, None)])
        proposals, outcomes = _attempt_all_proposals(repository, updates, box=_LOCATION_B_BOX)
        assert len(outcomes) == 1
        assert not outcomes[0].created
        assert outcomes[0].outcome == "reject_insufficient_detector_corroboration"

    def test_tracker_only_chained_weak_false_chain_is_rejected(self, repository: ProductRepository) -> None:
        """Hard-negative C: `visit-observation-candidate-027`'s own shape --
        many short, independently-restarted track generations at one static
        location (never strong, confidence 0.147-0.363 in the real case),
        each generation individually confirmed on the bare 2-detection
        floor and terminating via genuine `maximum_unsupported_duration`
        gaps before the next restart. Merged across all 4 generations here,
        `detection_count` sums to 8 (> the single-generation floor of 3) --
        proving this reproducer is *not* caught by the simpler count-only
        rule alone. It is caught because `merge_confidence_evidence` takes
        the *max*, never the sum, of `max_consecutive_detector_confirmed_
        frames`: no single restart ever showed 2 consecutive genuine
        detections, so chaining four bare-minimum restarts together cannot
        manufacture the depth one real sustained encounter would show (see
        `TestGenuineWeakPositivesAdmitted::test_sustained_multi_generation_
        activity_with_one_real_consecutive_segment_is_admitted` for the
        direct contrast)."""
        tracker = _tracker()
        updates: list[TrackUpdate] = []
        start = 0
        for confidence_pair in ((0.15, 0.18), (0.20, 0.16), (0.25, 0.19), (0.30, 0.22)):
            updates += _drive(tracker, [
                (start, (confidence_pair[0], _LOCATION_B_BOX)),
                (start + 500, None),
                (start + 1000, (confidence_pair[1], _LOCATION_B_BOX)),
            ])
            updates += _drive(tracker, [(start + 1000 + 5500, None)])  # forces maximum_unsupported_duration
            start += 1000 + 5500 + 1000  # next restart begins comfortably within merge_gap_ms (15s) of this one's end

        generation_ids = {u.generation_id for u in updates}
        tracklets = _build_tracklets(updates, box_by_generation={g: _LOCATION_B_BOX for g in generation_ids})
        assert len(generation_ids) == 4, "reproducer must yield four separate, independently-restarted generations"

        result = assemble_visit_episodes(tracklets)
        assert len(result.proposals) == 1, "four temporally-adjacent same-geometry generations must merge into one proposal"
        proposal = result.proposals[0]
        assert len(proposal.constituent_generation_ids) == 4
        assert proposal.confidence_evidence.detection_count == 8
        assert proposal.confidence_evidence.strong_detection_count == 0
        assert proposal.confidence_evidence.max_consecutive_detector_confirmed_frames == 1

        _activate(repository)
        candidates = tuple(
            candidate
            for generation_id in proposal.constituent_generation_ids
            for candidate in _evidence_candidates_for(generation_id, _LOCATION_B_BOX)
        )
        evidence_bytes = {candidate.media_asset_id: JPEG_BYTES for candidate in candidates}
        outcome = _adapter(repository).attempt_candidate(
            proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=BASE_TIME,
        )
        assert not outcome.created
        assert outcome.outcome == "reject_insufficient_detector_corroboration"

    def test_rejection_is_not_keyed_to_either_known_field_location(self, repository: ProductRepository) -> None:
        """Adversarial self-review (this milestone's own explicit
        instruction): the same weak/minimal/non-consecutive structural
        signature, at a bounding box nothing like either reported v8/v9
        location (top-left corner of frame, not the road-side foliage or
        the feeder cap), is rejected identically -- proving the rule is a
        semantic corroboration-structure rule, not scene-coordinate
        memorization of the two known field locations."""
        arbitrary_box = (0.03, 0.03, 0.09, 0.09)
        tracker = _tracker()
        updates = _drive(tracker, [
            (0, (0.22, arbitrary_box)),
            (250, None),
            (500, (0.17, arbitrary_box)),
        ])
        updates += _drive(tracker, [(6500, None)])
        _, outcomes = _attempt_all_proposals(repository, updates, box=arbitrary_box)
        assert outcomes[0].outcome == "reject_insufficient_detector_corroboration"

    def test_drifting_weak_minimal_signal_is_still_rejected(self, repository: ProductRepository) -> None:
        """Motion is not truth in either direction (this milestone's own
        explicit instruction): the fix must not accidentally key on
        *staleness* of position either -- a weak, minimally-corroborated
        signal that drifts slightly between its two genuine detections
        (the same shape a lucky pair of wind-blown-foliage noise hits could
        produce) is rejected exactly the same way a perfectly static one
        is, because this check never reads geometry at all."""
        box_1 = (0.16, 0.66, 0.24, 0.74)
        box_2 = (0.18, 0.67, 0.26, 0.75)
        tracker = _tracker()
        updates = _drive(tracker, [
            (0, (0.16, box_1)),
            (250, None),
            (500, (0.19, box_2)),
        ])
        updates += _drive(tracker, [(6500, None)])
        _, outcomes = _attempt_all_proposals(repository, updates, box=box_2)
        assert outcomes[0].outcome == "reject_insufficient_detector_corroboration"


# --------------------------------------------------------------------------
# Genuine weak-bird positive controls -- must continue to admit.
# --------------------------------------------------------------------------


class TestGenuineWeakPositivesAdmitted:
    def test_small_distant_bird_is_admitted(self, repository: ProductRepository) -> None:
        """Weak (never strong) throughout, but genuinely present for longer
        -- five real detections as it forages, well past the bare
        corroboration floor even though individually low-confidence."""
        box = (0.30, 0.30, 0.34, 0.34)  # small subject area, realistic for a distant bird
        tracker = _tracker()
        updates = _drive(tracker, [
            (0, (0.22, box)), (250, None), (500, (0.28, box)), (750, None),
            (1000, (0.24, box)), (1250, None), (1500, (0.31, box)), (1750, None),
            (2000, (0.26, box)),
        ])
        updates += _finalize(tracker)
        _, outcomes = _attempt_all_proposals(repository, updates, box=box)
        assert outcomes[0].created
        assert outcomes[0].outcome == "created"

    def test_brief_landing_and_departure_is_admitted(self, repository: ProductRepository) -> None:
        """Present only briefly, but genuinely present -- consecutive
        real detections while it is actually there produce a real
        back-to-back streak, distinguishing a genuine brief visitor from an
        isolated noise blip even though the whole encounter is short."""
        box = (0.55, 0.40, 0.62, 0.50)
        tracker = _tracker()
        updates = _drive(tracker, [
            (0, (0.35, box)), (250, (0.40, box)), (500, (0.33, box)),
        ])
        updates += _finalize(tracker)
        _, outcomes = _attempt_all_proposals(repository, updates, box=box)
        assert outcomes[0].created

    def test_low_confidence_but_visually_real_bird_sitting_still_is_admitted(self, repository: ProductRepository) -> None:
        """Never strong and nearly stationary (a genuinely perched,
        backlit, or otherwise weakly-detected real bird) -- this check
        reads only corroboration count/streak, never geometry stability,
        so a real bird that happens to sit still is not penalized for it;
        real, repeated re-confirmation as it sits carries it past the
        floor."""
        box = (0.60, 0.20, 0.66, 0.28)
        tracker = _tracker()
        updates = _drive(tracker, [
            (0, (0.30, box)), (250, None), (500, (0.29, box)), (750, None),
            (1000, (0.32, box)), (1250, None), (1500, (0.31, box)),
        ])
        updates += _finalize(tracker)
        _, outcomes = _attempt_all_proposals(repository, updates, box=box)
        assert outcomes[0].created

    def test_partially_occluded_bird_is_admitted(self, repository: ProductRepository) -> None:
        """Inconsistent, gap-interrupted weak detections (simulating
        partial occlusion by a branch/feeder edge) still accumulate real
        corroboration over a longer window."""
        box = (0.70, 0.55, 0.76, 0.63)
        tracker = _tracker()
        updates = _drive(tracker, [
            (0, (0.24, box)), (250, None), (500, None), (750, (0.27, box)),
            (1000, None), (1250, (0.21, box)), (1500, None), (1750, None),
            (2000, (0.29, box)),
        ])
        updates += _finalize(tracker)
        _, outcomes = _attempt_all_proposals(repository, updates, box=box)
        assert outcomes[0].created

    def test_intermittently_corroborated_bird_is_admitted(self, repository: ProductRepository) -> None:
        """Sparse, always non-consecutive corroboration spread over a
        longer duration -- the required "intermittent detector
        corroboration" positive control. Never one 2-in-a-row streak
        anywhere, so this specifically exercises the count-based escape
        (not the streak-based one), proving the two axes are independently
        sufficient, not both required."""
        box = (0.12, 0.45, 0.18, 0.53)
        tracker = _tracker()
        updates = _drive(tracker, [
            (0, (0.20, box)), (500, None), (1000, None), (1500, (0.23, box)),
            (2000, None), (2500, None), (3000, (0.19, box)), (3500, None),
            (4000, None), (4500, (0.25, box)),
        ])
        updates += _finalize(tracker)
        _, outcomes = _attempt_all_proposals(repository, updates, box=box)
        assert outcomes[0].created
        assert outcomes[0].outcome == "created"

    def test_sustained_multi_generation_activity_with_one_real_consecutive_segment_is_admitted(
        self, repository: ProductRepository,
    ) -> None:
        """Direct contrast with `TestHardNegativesRejected::test_tracker_
        only_chained_weak_false_chain_is_rejected`: the same *shape*
        (several short, independently-restarted generations at one
        location, none individually strong) is admitted when -- unlike the
        false chain -- at least one restart shows a genuine 2-consecutive-
        frame detector streak somewhere in the whole encounter, proving
        `merge_confidence_evidence`'s max-not-sum handling correctly
        preserves real sustained/repeated activity rather than rejecting
        every multi-generation weak proposal indiscriminately."""
        box = (0.85, 0.15, 0.91, 0.23)
        tracker = _tracker()
        updates: list[TrackUpdate] = []
        start = 0
        # First two restarts: bare-minimum, non-consecutive (same shape as
        # the false chain).
        for confidence_pair in ((0.20, 0.24), (0.18, 0.22)):
            updates += _drive(tracker, [
                (start, (confidence_pair[0], box)), (start + 500, None), (start + 1000, (confidence_pair[1], box)),
            ])
            updates += _drive(tracker, [(start + 1000 + 5500, None)])
            start += 1000 + 5500 + 1000
        # Third restart: two genuinely *consecutive* detections -- the real
        # corroboration depth a false static confusor's own repeated bare-
        # minimum restarts never show.
        updates += _drive(tracker, [(start, (0.26, box)), (start + 250, (0.29, box))])
        updates += _finalize(tracker)

        generation_ids = {u.generation_id for u in updates}
        tracklets = _build_tracklets(updates, box_by_generation={g: box for g in generation_ids})
        result = assemble_visit_episodes(tracklets)
        assert len(result.proposals) == 1
        proposal = result.proposals[0]
        assert len(proposal.constituent_generation_ids) == 3
        assert proposal.confidence_evidence.max_consecutive_detector_confirmed_frames == 2

        _activate(repository)
        candidates = tuple(
            candidate
            for generation_id in proposal.constituent_generation_ids
            for candidate in _evidence_candidates_for(generation_id, box)
        )
        evidence_bytes = {candidate.media_asset_id: JPEG_BYTES for candidate in candidates}
        outcome = _adapter(repository).attempt_candidate(
            proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=BASE_TIME,
        )
        assert outcome.created


# --------------------------------------------------------------------------
# Strong positives -- normal Visits, entirely unaffected.
# --------------------------------------------------------------------------


class TestStrongPositiveUnaffected:
    def test_normal_confident_visit_is_admitted_unchanged(self, repository: ProductRepository) -> None:
        box = (0.40, 0.40, 0.50, 0.50)
        tracker = _tracker()
        updates = _drive(tracker, [(0, (0.87, box)), (250, (0.91, box))])
        updates += _finalize(tracker)
        _, outcomes = _attempt_all_proposals(repository, updates, box=box)
        assert outcomes[0].created
        assert outcomes[0].outcome == "created"


# --------------------------------------------------------------------------
# Multi-subject safety -- no cross-subject corroboration.
# --------------------------------------------------------------------------


class TestMultiSubjectSafety:
    def test_weak_real_sibling_is_not_killed_by_a_strong_simultaneous_sibling(
        self, repository: ProductRepository,
    ) -> None:
        """Two simultaneous, disjoint-geometry subjects in the same frames:
        one strong (trivially admitted on its own merits) and one weak but
        genuinely present (five real detections, never strong -- admitted
        on the count-based escape, exactly like `test_small_distant_bird_
        is_admitted`). Each subject's own `confidence_evidence` must decide
        its own fate, never borrowing the other's strength."""
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

        # Two disjoint generations, each keyed to its own real geometry --
        # `build_tracklets` groups purely by `generation_id`, so mapping
        # every generation to its own actual box (not a shared constant)
        # matters here, unlike every single-location reproducer above.
        # Neither subject ever moves, so every one of a generation's own
        # updates (detected or tracker-supported alike) reports the exact
        # same literal box -- a reliable way to classify generation_id ->
        # subject without needing the tracker's own internal state.
        box_by_generation = {u.generation_id: (strong_box if u.bounding_box == strong_box else weak_box) for u in updates}
        tracklets = _build_tracklets(updates, box_by_generation=box_by_generation)
        assert len(tracklets) == 2
        result = assemble_visit_episodes(tracklets)
        assert len(result.proposals) == 2  # genuinely simultaneous, disjoint subjects never merge

        _activate(repository)
        adapter = _adapter(repository)
        outcomes_by_box: dict[tuple[float, ...], object] = {}
        for proposal in result.proposals:
            generation_id = proposal.constituent_generation_ids[0]
            tracklet = next(t for t in tracklets if t.generation_id == generation_id)
            box = tracklet.geometry_envelope
            candidates = _evidence_candidates_for(generation_id, box)
            evidence_bytes = {candidate.media_asset_id: JPEG_BYTES for candidate in candidates}
            outcome = adapter.attempt_candidate(
                proposal, evidence_candidates=candidates, evidence_bytes=evidence_bytes, observed_at=BASE_TIME,
            )
            outcomes_by_box[box] = outcome
            assert outcome.created, f"sibling at {box} must be admitted on its own evidence"

        assert len(outcomes_by_box) == 2
        # No cross-subject corroboration: the weak sibling's own proposal
        # never carries the strong sibling's detections.
        weak_proposal = next(p for p in result.proposals if p.confidence_evidence.strong_detection_count == 0)
        assert weak_proposal.confidence_evidence.detection_count == 4


# --------------------------------------------------------------------------
# Species-escalation trace (Option A: rejection at admission structurally
# eliminates the issue -- see docs/hard-negative-visit-admission-precision-
# species-escalation-correctness-v1-report.md "Species-escalation result").
# --------------------------------------------------------------------------


class TestSpeciesEscalation:
    def test_rejected_hard_negative_never_becomes_a_visit_species_inference_could_reach(
        self, repository: ProductRepository,
    ) -> None:
        """Every production species-inference entry point (the automatic
        Observation Engine v2 path, the legacy live-motion path, and the
        manual `POST /api/review-queue/{target_type}/{target_id}/identify`
        action) requires a pre-existing `VisitModel` row to resolve at all
        (`ProductRepository._review_identification_item_for_visit` raises
        `missing_visit` otherwise). A proposal rejected here at admission
        creates neither a `VisitModel` nor an `EventModel` row (`outcome.
        visit_id`/`event_id` are both `None`) -- so `visit-observation-
        candidate-026`'s own real shape (reproduced in `TestHardNegatives
        Rejected::test_location_b_glint_static_object_chain_is_rejected`,
        the one v9 confirmed-false Visit that received a confident wrong
        species label) can now never reach species inference at all,
        confirmed directly against the real repository rather than assumed
        from code reading alone."""
        tracker = _tracker()
        updates = _drive(tracker, [
            (0, (0.109, _LOCATION_B_BOX)), (250, None), (500, (0.111, _LOCATION_B_BOX)),
            (750, None), (1000, (0.110, _LOCATION_B_BOX)),
        ])
        updates += _drive(tracker, [(6500, None)])
        proposals, outcomes = _attempt_all_proposals(repository, updates, box=_LOCATION_B_BOX)

        outcome = outcomes[0]
        assert not outcome.created
        assert outcome.visit_id is None
        assert outcome.event_id is None

        with repository.session_factory() as session:
            # No Visit row was created *for this proposal* -- confirmed
            # directly (never a bare row-count, which the repository's own
            # demo-seed data would confound): the ledger row that would
            # normally carry `visit_id` for this exact `proposal_id` does
            # not exist at all.
            assert session.get(ObservationCandidateVisitModel, proposals[0].proposal_id) is None
            # A made-up visit id shaped like what this proposal *would* have
            # produced resolves nowhere -- the one precondition every real
            # identification entry point (`_review_identification_item_for_
            # visit`) requires before it can run at all.
            with pytest.raises(ValueError, match="missing_visit"):
                repository._review_identification_item_for_visit(session, "visit-observation-candidate-nonexistent")


# --------------------------------------------------------------------------
# Reviewed-truth safety -- an unrelated rejection must not disturb an
# already-reviewed Visit.
# --------------------------------------------------------------------------


class TestReviewedTruthPreserved:
    def test_unrelated_hard_negative_rejection_does_not_disturb_a_reviewed_visit(
        self, repository: ProductRepository,
    ) -> None:
        strong_box = (0.40, 0.40, 0.50, 0.50)
        tracker = _tracker()
        strong_updates = _drive(tracker, [(0, (0.90, strong_box)), (250, (0.92, strong_box))])
        strong_updates += _finalize(tracker)
        strong_proposals, strong_outcomes = _attempt_all_proposals(repository, strong_updates, box=strong_box)
        assert strong_outcomes[0].created
        visit_id = strong_outcomes[0].visit_id
        assert visit_id is not None

        from mockingbird.api.schemas import ReviewCorrectionCreate

        repository.create_review_label(
            ReviewCorrectionCreate(
                target_type="visit", target_id=visit_id, label="northern_cardinal",
                review_origin="human", reviewer_identity="reviewer@example.test",
            ),
            BASE_TIME + timedelta(minutes=1),
        )
        with repository.session_factory() as session:
            reviewed_visit = session.get(VisitModel, visit_id)
            assert reviewed_visit is not None
            assert reviewed_visit.review_status == "reviewed"
            assert reviewed_visit.reviewed_label == "northern_cardinal"

        # A wholly unrelated hard-negative-shaped proposal is rejected, on a
        # different Stream location, same session.
        hard_negative_tracker = _tracker()
        hard_negative_updates = _drive(hard_negative_tracker, [
            (10_000, (0.15, _LOCATION_A_BOX)), (10_250, None), (10_500, (0.18, _LOCATION_A_BOX)),
        ])
        hard_negative_updates += _drive(hard_negative_tracker, [(17_000, None)])
        _, hard_negative_outcomes = _attempt_all_proposals(repository, hard_negative_updates, box=_LOCATION_A_BOX)
        assert not hard_negative_outcomes[0].created

        with repository.session_factory() as session:
            reviewed_visit = session.get(VisitModel, visit_id)
            assert reviewed_visit is not None
            assert reviewed_visit.review_status == "reviewed"
            assert reviewed_visit.reviewed_label == "northern_cardinal"


# --------------------------------------------------------------------------
# Rate-limit interaction (this milestone's own explicit instruction): a
# rejected hard negative must not consume the same rolling `max_candidates_
# per_hour`/`max_candidates_per_session` capacity an admitted wildlife Visit
# does.
# --------------------------------------------------------------------------


class TestRateLimitInteraction:
    def test_rejected_hard_negatives_do_not_consume_candidate_rate_limit_capacity(
        self, repository: ProductRepository,
    ) -> None:
        """`candidates_created_in_session`/`candidates_created_in_trailing_
        hour` (the two counters `evaluate_candidate_authority`'s own rate
        -limit gate actually reads) are derived from `ObservationCandidateVisitModel`
        row *creation* only (`product_repository._authority_state`) -- a
        proposal this new quality-gate check rejects never reaches that
        insert (confirmed structurally in `TestSpeciesEscalation` above: no
        ledger row exists for it at all), so it can never count against
        either budget, exactly like every other pre-existing quality
        -gate/authority rejection already did not. `candidates_attempted_
        count` (a separate, diagnostic-only counter, never read by the
        rate-limit gate itself) *does* still increment -- rejected attempts
        remain honestly visible in diagnostics, just never billed against
        the budget an admitted Visit consumes."""
        _activate(repository)
        before = repository.get_observation_authority_state(stream_id=STREAM_ID)
        assert before.candidates_created_in_session == 0
        assert before.candidates_created_in_trailing_hour == 0

        for index in range(3):
            offset = index * 20_000
            tracker = _tracker()
            updates = _drive(tracker, [
                (offset, (0.15, _LOCATION_A_BOX)), (offset + 250, None), (offset + 500, (0.18, _LOCATION_A_BOX)),
            ])
            updates += _drive(tracker, [(offset + 6500, None)])
            _, outcomes = _attempt_all_proposals(repository, updates, box=_LOCATION_A_BOX)
            assert not outcomes[0].created
            assert outcomes[0].outcome == "reject_insufficient_detector_corroboration"

        after = repository.get_observation_authority_state(stream_id=STREAM_ID)
        assert after.candidates_created_in_session == 0
        assert after.candidates_created_in_trailing_hour == 0
        assert after.candidates_created_count == 0
        assert after.candidates_attempted_count == 3
