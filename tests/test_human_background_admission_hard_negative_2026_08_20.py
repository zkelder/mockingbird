"""Person / Background False-Positive Attribution & Admission Precision v1.

Deterministic hard-negative regression fixture for a real, directly-verified
field defect: `visit-observation-candidate-139`/`-140` from the accepted
2026-08-20 Cache-128 Live Daylight Acceptance v1 session
(`stream-ca892992771c`, see
docs/cache-128-live-daylight-acceptance-v1-report.md S6) were both admitted
as `needs_review` wildlife Visits, then both received a confident BioCLIP
bird-species label (`brown_thrasher`/`red_bellied_woodpecker`), although
neither Visit's own persisted evidence shows a bird. Both fall exactly
inside the independently-reviewed window covering a person walking a dog on
a leash. Directly re-fetched from the live product database and re-viewed
this milestone (see
docs/person-background-false-positive-attribution-v1-report.md): the real
`classifier_same_frame` evidence crops for both Visits show a person (and,
for Visit 140, a dog on a leash) walking across the yard/street, no bird
anywhere, at the exact recorded geometry reproduced below.

Every numeric/geometric/identity fact below (offsets, per-detection
confidence samples, bounding boxes, generation/track/proposal ids,
`broad_class`) is copied verbatim from the real, persisted
`observation_candidate_visits.confidence_evidence_json`/lineage columns for
these two rows -- recovered directly from the deployed product's own
database via a read-only query, commit `bdb59f5`, schema 35 -- never
fabricated, estimated, or inferred. `terminal_reason` on the synthetic
`Tracklet`s below is the one fact this checkout could not recover (the
live session's in-memory counterfactual ledger does not survive past
`session.stop()`, and this field is not persisted to
`observation_candidate_visits`); it is set to an explicit placeholder that
does not affect either assertion below (`classify_boundary` only reads it
on the `keep_separate` path, never reached here -- see
`test_the_two_tracks_are_correctly_never_merged_as_one_visit`). No image
bytes are included anywhere in this file: `_real_jpeg_bytes()` below is a
small synthetic solid-color placeholder, never the real evidence
photograph -- this repository never commits raw private field media (see
docs/public-benchmark-governance.md's consent boundary for anything that
could identify a real person or property).

**Root cause, established by the milestone's own full funnel trace (see the
report above): the raw MDv5 detector itself -- correctly read and correctly
enforced by every downstream MockingBird stage -- classified this person's
partial view as `animal`-class at real, non-marginal confidence (up to
0.877, higher than every one of the ten genuine bird Visits admitted in the
same 90-minute session). This is not a MockingBird logic defect: the
tracker only ever tracks `is_animal=True` detections (the model's own
class output, unmodified/unmapped), the persisted evidence geometry is
provably undrifted (`geometry_evidence_gap_ms=0` for the same-frame crop
that fed species inference), and no swept confidence/count-based policy
could reject either case without also rejecting a real, same-session bird
(Visit 140 alone: `max_confidence=0.877` exceeds every one of the ten real
bird Visits' own `max_confidence` that session). Decision B: the real gap
is species-inference abstention (Gate B -- BioCLIP has no "not a bird"
outcome at all, a pre-existing, already-tracked regression class in
roadmap.md), not a fixable Gate-A admission mechanism.**

This test intentionally documents *today's real, understood* behavior for
the future Gate B "Identification Eligibility + Abstention v1" milestone to
change -- it does not assert desired product behavior. Do not "fix" this
test by loosening its assertions without a proven Gate-A mechanism; read
the milestone report first.
"""
from __future__ import annotations

from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from mockingbird.observation.admission_replay import IsolatedAdmissionRepository, evaluate_shadow_admission
from mockingbird.observation.contracts import ConfidenceEvidenceSummary, DetectionEvidenceSample, EvidenceCandidate
from mockingbird.observation.visit_episode_assembler import AssembledVisitProposal, Tracklet, classify_boundary

# Real Stream identity (pure-function `classify_boundary` test only -- no
# repository/isolation boundary applies there). The admission-layer test
# below uses a separate, `replay:`-prefixed identity instead, per
# `admission_replay.require_replay_stream_id`.
REAL_STREAM_ID = "stream-ca892992771c"
REPLAY_STREAM_ID = "replay:2026-08-20-human-background-hard-negative"

# The real session's own `POST .../observation/start` wall-clock moment --
# used only so `evaluate_shadow_admission`'s logical-time offsets land on a
# realistic base; no behavior depends on the exact value.
BASE_OBSERVED_AT = datetime(2026, 8, 20, 22, 25, 28, tzinfo=UTC)

# `classify_boundary` only reads `terminal_reason` on the `keep_separate`
# path (`earlier.terminal_reason == "negative_interval_reentry"`), which is
# never reached for this pair -- `_temporal_overlap` short-circuits first
# (see the test below). Not a recovered real fact; explicitly not one.
UNRECOVERED_TERMINAL_REASON = "not_recovered_session_ended"


def _real_jpeg_bytes(*, size: tuple[int, int] = (640, 480)) -> bytes:
    """A genuinely PIL-decodable JPEG -- `evidence_scoring._score` hard-
    rejects anything that isn't -- never the real evidence photograph. A
    plain solid-color placeholder, matching `test_admission_replay.py`'s
    own established convention for this exact need."""

    buffer = BytesIO()
    Image.new("RGB", size, color=(60, 90, 60)).save(buffer, format="JPEG")
    return buffer.getvalue()


JPEG_BYTES = _real_jpeg_bytes()


def _sample(
    *,
    confidence: float,
    source_offset_ms: int,
    frame_id: str,
    observation_id: str,
    is_strong: bool,
    bounding_box: tuple[float, float, float, float],
) -> DetectionEvidenceSample:
    return DetectionEvidenceSample(
        confidence=confidence,
        source_offset_ms=source_offset_ms,
        frame_id=frame_id,
        observation_id=observation_id,
        is_strong=is_strong,
        bounding_box=bounding_box,
    )


# --- Visit 139 (`visit-episode:c21ec095b00b179581146e96`) -------------------
# frame-track-0280 / stream-ca892992771c:frame-track:a1c04a60c009406ec260
V139_PROPOSAL_ID = "visit-episode:c21ec095b00b179581146e96"
V139_GENERATION_ID = "stream-ca892992771c:frame-track:a1c04a60c009406ec260"
V139_TRACK_ID = "frame-track-0280"
V139_START_OFFSET_MS = 5113499
V139_END_OFFSET_MS = 5120093
V139_SAMPLES = (
    _sample(confidence=0.138, source_offset_ms=5113499, frame_id="dcf43ac62dacb651ac310813ab8fcc4f73247f72cd172a0cb60965ab107bc6f1", observation_id="baa2924bd62d92e2937233633c095174786e521e480c6b63479be1ff846710ef", is_strong=False, bounding_box=(0.9854, 0.5287, 0.9999, 0.6138)),
    _sample(confidence=0.751, source_offset_ms=5114612, frame_id="c79241684c936f302025545d51c68aa0ec8cd372fa170cdea7eff843958f5c87", observation_id="0569807c255623fee5e5569c66dfc51f27352b4a6697b3561ceeabd1ddb58d82", is_strong=True, bounding_box=(0.8619, 0.5731, 0.9238, 0.6277)),
)
V139_CONFIDENCE_EVIDENCE = ConfidenceEvidenceSummary(
    detection_count=2,
    max_confidence=0.751,
    mean_confidence=0.4445,
    median_confidence=0.4445,
    strong_detection_count=1,
    weak_detection_count=1,
    max_consecutive_detector_confirmed_frames=1,
    samples=V139_SAMPLES,
    broad_class="animal",
    first_detection_offset_ms=5113499,
    last_detection_offset_ms=5114612,
    sample_truncated=False,
)
# Real persisted `normalized_track_box_json` on the "identification" media
# asset (`media-candidate-313`, 3840x2160) -- the actual evidence geometry a
# reviewer/BioCLIP would see, not the raw detector box.
V139_IDENTIFICATION_BOX = (0.8219, 0.5931000000000001, 0.8837999999999999, 0.6477)

# --- Visit 140 (`visit-episode:dccd797355839764dfab6ca0`) -------------------
# frame-track-0281 / stream-ca892992771c:frame-track:3ddb8f375c3d17e45232
V140_PROPOSAL_ID = "visit-episode:dccd797355839764dfab6ca0"
V140_GENERATION_ID = "stream-ca892992771c:frame-track:3ddb8f375c3d17e45232"
V140_TRACK_ID = "frame-track-0281"
V140_START_OFFSET_MS = 5119540
V140_END_OFFSET_MS = 5140928
V140_SAMPLES = (
    _sample(confidence=0.126, source_offset_ms=5119540, frame_id="b56e7aff6c4b5a48c587b308b8e5873917f10a78b4c3ab46948bfeecfb1731a4", observation_id="ef4c5e4c447765dd2dc856a0206bff76848bb174b4df5bbb4bb17f3dc6c7c379", is_strong=False, bounding_box=(0.4463, 0.4481, 0.4614, 0.4879)),
    _sample(confidence=0.135, source_offset_ms=5121762, frame_id="41fd62535759df7124b877c222fdbcf77537bbda291d1cdb5f2e9b15af59a94c", observation_id="39fd47360beb4e8da56290d29fe5dc0eb6081cb372e3aecabf926f9736484496", is_strong=False, bounding_box=(0.6057, 0.5175, 0.6301, 0.6258)),
    _sample(confidence=0.18, source_offset_ms=5122941, frame_id="613d6f861bfa61367fb59d64d979d4ba8e40c1ad46e55f579eb468da4969e199", observation_id="cabd7f00f0e09fdf77f06ca10931db5b170a722811df212a46eb231865a47147", is_strong=False, bounding_box=(0.6041, 0.5148, 0.6306, 0.6249)),
    _sample(confidence=0.139, source_offset_ms=5127382, frame_id="19e585b14d0143244f8836ca2ec5e492c6022d5d817292ab0cf3269cf51ff78a", observation_id="2fd313fd54ab6171bf49c3e8d4061a1632630effda4cc77e69630f76768372f8", is_strong=False, bounding_box=(0.6177, 0.6, 0.6562, 0.6518)),
    _sample(confidence=0.107, source_offset_ms=5128516, frame_id="3aa85daddbeaef20b0bfb2fca7d1c658877449c1a174714de730f1e9d63965a1", observation_id="a69fdbb5a22f2dcefdd04cec446209e2da6dc208fa7d06420e27664b4c97a587", is_strong=False, bounding_box=(0.6166, 0.6046, 0.6358, 0.6527)),
    _sample(confidence=0.509, source_offset_ms=5129627, frame_id="7f1e7391a9893bf416b4c99f01f80d59ee1b5d20fa819bc1a8dec16c18524d63", observation_id="6eebe3388b8b34928d54ca9e5005aea75c82bbe13b3f02276633634c6a3f137a", is_strong=False, bounding_box=(0.527, 0.6138, 0.5613, 0.66)),
    _sample(confidence=0.371, source_offset_ms=5130736, frame_id="3d2e938d956af36d5b69b35e50b9d4dc52d1c405a09ca3d6bb5b510af1fddb94", observation_id="6a38fd02722ed63fcfb69bdbf2080ae6d5011f2eff521d9a77497a866f0dbe4f", is_strong=False, bounding_box=(0.4447, 0.624, 0.4999, 0.6758)),
    _sample(confidence=0.432, source_offset_ms=5132495, frame_id="db458f27be4f18782ae60a9f76ec0aa3a90be2d47b83c4d791e6b6097c264a11", observation_id="6bea5231fce5dfbdc3ccf5c94e2d598edac662a9c3c72b810d7551b825d1fdc3", is_strong=False, bounding_box=(0.2984, 0.6518, 0.3301, 0.6943)),
    _sample(confidence=0.498, source_offset_ms=5133706, frame_id="30c57ce0c301c391b69dcef72e55da44c35829537f9fc1de7df2874ca266f47c", observation_id="3361a21bf053a5cbff3c045a6c55c94fa6b788312136dee95dfcfe6652ad2857", is_strong=False, bounding_box=(0.1911, 0.6416, 0.2556, 0.7045)),
    _sample(confidence=0.814, source_offset_ms=5134815, frame_id="a86961bc82f9612fc062c5ba0519fb49c79bd0a32377a3b5463cd67c171a51e2", observation_id="145d9fc50442c295a26fa06cec1b54676e7ecc8e70456dcb7cfc54fc370c6d73", is_strong=True, bounding_box=(0.1104, 0.674, 0.1697, 0.724)),
    _sample(confidence=0.877, source_offset_ms=5135925, frame_id="575d26f0cd6a4e6a323ef5fffba81440ab79902cbb56f5979e0005f0edc38b4f", observation_id="ee6e26d48a8a7a3314fd808bb4b49b8dc2fdd717549b5413cce64fc866cc2b72", is_strong=True, bounding_box=(0.0432, 0.6861, 0.0958, 0.7323)),
)
V140_CONFIDENCE_EVIDENCE = ConfidenceEvidenceSummary(
    detection_count=11,
    max_confidence=0.877,
    mean_confidence=0.3807272727272727,
    median_confidence=0.371,
    strong_detection_count=2,
    weak_detection_count=9,
    max_consecutive_detector_confirmed_frames=4,
    samples=V140_SAMPLES,
    broad_class="animal",
    first_detection_offset_ms=5119540,
    last_detection_offset_ms=5135925,
    sample_truncated=False,
)
# Real persisted `normalized_track_box_json` on the "identification" media
# asset (`media-candidate-316`, 3840x2160).
V140_IDENTIFICATION_BOX = (0.6057, 0.5175, 0.6301, 0.6258)


def test_the_two_tracks_are_correctly_never_merged_as_one_visit() -> None:
    """Track 280 (Visit 139) and track 281 (Visit 140) are almost certainly
    one continuous real-world passage (the same person-and-dog crossing):
    track 281 starts 553ms *before* track 280 ends
    (`V140_START_OFFSET_MS=5119540 < V139_END_OFFSET_MS=5120093`), and both
    carry `broad_class="animal"` on the same Stream. `classify_boundary`
    correctly, and by long-standing, deliberate design (see
    "Structural incompatibility" in docs/tracklet-visit-assembly-contract.md),
    never merges two temporally-overlapping confirmed tracklets -- it cannot
    safely tell "two simultaneous real subjects" apart from "one tracker-
    association artifact," and guessing wrong (fabricating one continuous
    identity) would be worse than the current, conservative behavior.

    This is *not* the sequential-fragmentation shape the Ambiguous-Boundary
    Transitive Fragmentation Closure v1 milestone fixed (`ambiguous_
    boundary`, a non-overlapping gap) and not the concurrent-sibling shape
    Multi-Subject Visit Assembly Phase 1/2 addresses (which groups, but
    still never merges, incompatible tracklets under one Event) -- it is the
    original, unmodified, self-consciously-accepted `temporal_overlap` rule,
    unrelated to any 2026-08-19/08-20 multi-subject work. Two Visits from
    one real passage is the correct, already-understood consequence of that
    rule once the underlying subject is (incorrectly) detected as `animal`
    twice, not a new assembly defect."""

    earlier = Tracklet(
        generation_id=V139_GENERATION_ID,
        stream_id=REAL_STREAM_ID,
        broad_class="animal",
        start_offset_ms=V139_START_OFFSET_MS,
        end_offset_ms=V139_END_OFFSET_MS,
        start_bounding_box=V139_SAMPLES[0].bounding_box,
        end_bounding_box=V139_SAMPLES[-1].bounding_box,
        geometry_envelope=V139_SAMPLES[-1].bounding_box,
        terminal_reason=UNRECOVERED_TERMINAL_REASON,
        track_ids=(V139_TRACK_ID,),
        confidence_evidence=V139_CONFIDENCE_EVIDENCE,
    )
    later = Tracklet(
        generation_id=V140_GENERATION_ID,
        stream_id=REAL_STREAM_ID,
        broad_class="animal",
        start_offset_ms=V140_START_OFFSET_MS,
        end_offset_ms=V140_END_OFFSET_MS,
        start_bounding_box=V140_SAMPLES[0].bounding_box,
        end_bounding_box=V140_SAMPLES[-1].bounding_box,
        geometry_envelope=V140_SAMPLES[0].bounding_box,
        terminal_reason=UNRECOVERED_TERMINAL_REASON,
        track_ids=(V140_TRACK_ID,),
        confidence_evidence=V140_CONFIDENCE_EVIDENCE,
    )

    decision = classify_boundary(earlier, later)

    assert decision.decision == "incompatible"
    assert decision.reason == "temporal_overlap"


def test_both_proposals_reach_real_visit_creation_today(tmp_path: Path) -> None:
    """The deterministic RED this milestone exists to demonstrate: fed the
    exact real confidence/geometry/timing facts recovered from Visits
    139/140, the real, unmodified Stage 7 admission path
    (`candidate_visit_authority.evaluate_candidate_authority` +
    `candidate_quality_gate.evaluate_evidence_admission`, via
    `evaluate_shadow_admission`) creates a Visit for *both* -- reproducing,
    against an isolated/disposable repository, the exact real production
    outcome for this exact real evidence. Confirms the milestone's own
    finding that no existing Gate-A signal (authority mode/activation/
    lineage/ambiguity/budget, or evidence geometry/role validity) rejects
    this evidence, because none of those checks ever read detector
    confidence or class plausibility -- only whether a confirmed,
    `is_animal=True` track produced geometrically-valid evidence, which it
    genuinely did here."""

    proposal_139 = AssembledVisitProposal(
        proposal_id=V139_PROPOSAL_ID,
        stream_id=REPLAY_STREAM_ID,
        broad_class="animal",
        start_offset_ms=V139_START_OFFSET_MS,
        end_offset_ms=V139_END_OFFSET_MS,
        constituent_generation_ids=(V139_GENERATION_ID,),
        constituent_track_ids=(V139_TRACK_ID,),
        supporting_frame_ids=tuple(sample.frame_id for sample in V139_SAMPLES if sample.frame_id),
        source_capture_frame_ids=(),  # real recovered value: `[]` (a live session, never a reviewed-replay proposal)
        evidence_candidate_ids=("replay:139-identification",),
        assembly_decisions=(),  # singleton proposal: one constituent generation, zero internal merges
        ambiguous_adjacent_proposal_ids=(),  # real recovered value: `[]`
        confidence_evidence=V139_CONFIDENCE_EVIDENCE,
    )
    proposal_140 = AssembledVisitProposal(
        proposal_id=V140_PROPOSAL_ID,
        stream_id=REPLAY_STREAM_ID,
        broad_class="animal",
        start_offset_ms=V140_START_OFFSET_MS,
        end_offset_ms=V140_END_OFFSET_MS,
        constituent_generation_ids=(V140_GENERATION_ID,),
        constituent_track_ids=(V140_TRACK_ID,),
        supporting_frame_ids=tuple(sample.frame_id for sample in V140_SAMPLES if sample.frame_id),
        source_capture_frame_ids=(),
        evidence_candidate_ids=("replay:140-identification",),
        assembly_decisions=(),
        ambiguous_adjacent_proposal_ids=(),
        confidence_evidence=V140_CONFIDENCE_EVIDENCE,
    )
    evidence = (
        EvidenceCandidate(
            media_asset_id="replay:139-identification",
            stream_id=REPLAY_STREAM_ID,
            role="identification",
            captured_at=BASE_OBSERVED_AT,
            frame_id="replay:139-identification",
            source_offset_ms=V139_START_OFFSET_MS,
            width=3840,
            height=2160,
            subject_geometry=V139_IDENTIFICATION_BOX,
            track_generation_id=V139_GENERATION_ID,
        ),
        EvidenceCandidate(
            media_asset_id="replay:140-identification",
            stream_id=REPLAY_STREAM_ID,
            role="identification",
            captured_at=BASE_OBSERVED_AT,
            frame_id="replay:140-identification",
            source_offset_ms=V140_START_OFFSET_MS,
            width=3840,
            height=2160,
            subject_geometry=V140_IDENTIFICATION_BOX,
            track_generation_id=V140_GENERATION_ID,
        ),
    )
    evidence_bytes = {
        "replay:139-identification": JPEG_BYTES,
        "replay:140-identification": JPEG_BYTES,
    }

    with IsolatedAdmissionRepository(
        directory=tmp_path, stream_id=REPLAY_STREAM_ID, activation_boundary_at=BASE_OBSERVED_AT,
    ) as repository:
        report = evaluate_shadow_admission(
            (proposal_139, proposal_140),
            repository=repository,
            stream_id=REPLAY_STREAM_ID,
            evidence_candidates=evidence,
            evidence_bytes=evidence_bytes,
            base_observed_at=BASE_OBSERVED_AT,
        )

    # Today's real, documented behavior: both proposals are admitted --
    # human/background evidence reaches wildlife Visit creation, for the
    # same reason as the real Visits 139/140. See the module docstring:
    # this is Decision B (Gate B abstention), not a Gate-A code defect --
    # do not "fix" this assertion without a proven Gate-A mechanism.
    assert report.outcome_counts.get("created") == 2
    by_id = {outcome.proposal_id: outcome for outcome in report.outcomes}
    assert by_id[V139_PROPOSAL_ID].outcome == "created"
    assert by_id[V140_PROPOSAL_ID].outcome == "created"
