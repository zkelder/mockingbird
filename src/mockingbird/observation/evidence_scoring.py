"""Deterministic, bounded scoring of temporary Observation Engine evidence.

The scorer is provider-neutral and side-effect free.  It consumes only retained
candidate facts and optional image bytes/paths; it never performs model inference
or changes the persisted effective-primary selection.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Mapping

from PIL import Image, ImageFilter, ImageStat

from mockingbird.observation.contracts import EvidenceCandidate, VisitProposal


EVIDENCE_SCORING_VERSION = "multi-frame-evidence-v1"


@dataclass(frozen=True)
class EvidenceScoringBounds:
    max_candidates: int = 16
    max_analysis_frame_bytes: int = 8 * 1024 * 1024
    max_burst_frames: int = 3
    max_temporary_bytes: int = 32 * 1024 * 1024
    max_decoded_images: int = 12
    max_candidate_metadata_bytes: int = 64 * 1024
    max_alternates: int = 3
    max_sequence_frames: int = 8
    max_contact_sheet_bytes: int = 4 * 1024 * 1024

    def __post_init__(self) -> None:
        if not all(value > 0 for value in asdict(self).values()):
            raise ValueError("invalid_evidence_scoring_bounds")


@dataclass(frozen=True)
class EvidenceCandidateScore:
    candidate_id: str
    role: str
    source_frame_identity: str | None
    captured_at: datetime | None
    width: int | None
    height: int | None
    subject_geometry: tuple[float, float, float, float] | None
    temporal_status: str
    containment_status: str
    edge_clipping_status: str
    sharpness_category: str
    subject_area_ratio: float | None
    subject_pixel_area: int | None
    track_support_facts: tuple[tuple[str, int | float | bool | str | None], ...]
    component_scores: tuple[tuple[str, int], ...]
    identification_score: int
    context_score: int
    eligible: bool
    reason_codes: tuple[str, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceSelection:
    proposal_key: str
    track_generation_id: str | None
    candidate_scores: tuple[EvidenceCandidateScore, ...]
    identification_candidate_id: str | None
    context_candidate_id: str | None
    alternate_candidate_ids: tuple[str, ...]
    sequence_frame_ids: tuple[str, ...]
    no_useful_evidence: bool
    decoded_images_evaluated: int
    temporary_bytes_evaluated: int
    limitations: tuple[str, ...]
    semantic_fingerprint: str

    def score_for(self, candidate_id: str) -> EvidenceCandidateScore:
        return next(item for item in self.candidate_scores if item.candidate_id == candidate_id)


_IDENTIFICATION_ROLE = {
    "tracked_best": 30,
    "high_resolution_burst": 20,
    "detector_confirmed": 20,
    "snapshot_best_frame": 18,
    "final_supported": 16,
    "alternate": 10,
    "alternative": 10,
    "snapshot_context": 5,
    "context": 5,
    "pretrigger": 3,
}
_CONTEXT_ROLE = {
    "pretrigger": 30,
    "context": 28,
    "snapshot_context": 28,
    "final_supported": 18,
    "detector_confirmed": 15,
    "tracked_best": 14,
    "snapshot_best_frame": 14,
    "alternate": 10,
    "alternative": 10,
    "high_resolution_burst": 5,
}
_HARD_REJECTIONS = {
    "candidate_unavailable", "candidate_undecodable", "privacy_masked",
    "burst_subject_unverified", "subject_edge_clipped", "subject_absent",
}

# Broader Wildlife Maturity v1: a structural floor, not a tuned cutoff (no
# real MockingBird-camera mammal imagery exists to fit one against -- see
# docs/broader-wildlife-maturity-v1-contract.md). A large-bodied subject at
# ordinary camera-trap range (deer, raccoon, fox) routinely fills or exceeds
# the frame; edge contact there is the normal framing reality of a big,
# close, well-resolved subject, not a sign of a poor/partial detection the
# way it is for a typical small-bird sliver. 0.04 (4% of frame area) sits
# well above a typical bird crop's real measured range (roughly 0.3%-1.1% of
# frame area per docs/identification-eligibility-abstention-v1-report.md's
# bbox-coverage data), so ordinary bird-scale clipped detections keep today's
# unchanged hard-rejection behavior.
LARGE_SUBJECT_AREA_RATIO_FLOOR = 0.04


def score_proposal_evidence(
    proposal: VisitProposal,
    candidates: tuple[EvidenceCandidate, ...],
    *,
    media: Mapping[str, bytes | str | Path] | None = None,
    bounds: EvidenceScoringBounds | None = None,
) -> EvidenceSelection:
    """Rank one proposal's retained candidates without writes or inference."""

    limits = bounds or EvidenceScoringBounds()
    available_ids = set(proposal.evidence_media_asset_ids)
    media_lookup = media or {}
    deduplicated: dict[str, EvidenceCandidate] = {}
    for candidate in sorted(candidates, key=lambda item: _candidate_selection_order(item, media_lookup)):
        if candidate.media_asset_id not in available_ids:
            continue
        if (
            proposal.track_generation_id is not None
            and candidate.track_generation_id is not None
            and candidate.track_generation_id != proposal.track_generation_id
        ):
            continue
        deduplicated.setdefault(candidate.media_asset_id, candidate)
    bounded = tuple(deduplicated.values())[: limits.max_candidates]
    limitations: list[str] = []
    if len(deduplicated) > len(bounded):
        limitations.append("candidate_limit_reached")

    scores: list[EvidenceCandidateScore] = []
    decoded = 0
    evaluated_bytes = 0
    burst_count = 0
    metadata_bytes = 0
    for candidate in bounded:
        encoded_metadata = len(repr(candidate).encode("utf-8"))
        if metadata_bytes + encoded_metadata > limits.max_candidate_metadata_bytes:
            limitations.append("candidate_metadata_limit_reached")
            break
        metadata_bytes += encoded_metadata
        if candidate.role == "high_resolution_burst":
            burst_count += 1
            if burst_count > limits.max_burst_frames:
                limitations.append("burst_frame_limit_reached")
                continue
        image_value = (media or {}).get(candidate.media_asset_id)
        image_bytes = _media_bytes(image_value)
        image = None
        decode_allowed = decoded < limits.max_decoded_images
        byte_limit = limits.max_analysis_frame_bytes if candidate.role != "high_resolution_burst" else limits.max_temporary_bytes
        if image_bytes is not None and len(image_bytes) <= byte_limit and evaluated_bytes + len(image_bytes) <= limits.max_temporary_bytes:
            if decode_allowed:
                image = _decode(image_bytes)
                decoded += 1
                evaluated_bytes += len(image_bytes)
            else:
                limitations.append("decoded_image_limit_reached")
        elif image_bytes is not None:
            limitations.append("temporary_byte_limit_reached")
        scores.append(_score(candidate, image=image, image_supplied=image_value is not None))

    ordered_scores = tuple(sorted(scores, key=lambda item: item.candidate_id))
    identification = _best(ordered_scores, context=False)
    context = _best(ordered_scores, context=True)
    used = {item for item in (identification, context) if item is not None}
    alternates = tuple(
        item.candidate_id
        for item in sorted(
            (item for item in ordered_scores if item.eligible and item.candidate_id not in used),
            key=lambda item: (-item.identification_score, item.candidate_id),
        )[: limits.max_alternates]
    )
    sequence = tuple(dict.fromkeys(
        item.source_frame_identity for item in sorted(
            ordered_scores,
            key=lambda item: (
                _candidate_offset(deduplicated[item.candidate_id]), item.source_frame_identity or "",
            ),
        ) if item.source_frame_identity
    ))[: limits.max_sequence_frames]
    semantic = {
        "version": EVIDENCE_SCORING_VERSION,
        "proposal_key": proposal.proposal_key,
        "track_generation_id": proposal.track_generation_id,
        "candidate_scores": [asdict(item) for item in ordered_scores],
        "identification_candidate_id": identification,
        "context_candidate_id": context,
        "alternate_candidate_ids": alternates,
        "sequence_frame_ids": sequence,
        "no_useful_evidence": identification is None and context is None,
        "limitations": sorted(set(limitations)),
    }
    from mockingbird.observation.replay import semantic_fingerprint
    return EvidenceSelection(
        proposal.proposal_key,
        proposal.track_generation_id,
        ordered_scores,
        identification,
        context,
        alternates,
        sequence,
        identification is None and context is None,
        decoded,
        evaluated_bytes,
        tuple(sorted(set(limitations))),
        semantic_fingerprint(semantic),
    )


def _score(
    candidate: EvidenceCandidate,
    *,
    image: Image.Image | None,
    image_supplied: bool,
) -> EvidenceCandidateScore:
    facts = dict(candidate.quality_facts)
    reasons: set[str] = set()
    limitations: set[str] = set()
    components: dict[str, int] = {}

    declared_decodable = facts.get("decodable")
    if image is None and declared_decodable is not True:
        reasons.add("candidate_undecodable" if image_supplied else "candidate_unavailable")
    dimensions = (
        candidate.width if isinstance(candidate.width, int) and candidate.width > 0 else image.size[0] if image is not None else None,
        candidate.height if isinstance(candidate.height, int) and candidate.height > 0 else image.size[1] if image is not None else None,
    )
    width, height = dimensions
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        reasons.add("candidate_unavailable")

    geometry = candidate.subject_geometry
    area_ratio = None
    pixel_area = None
    containment = "unavailable"
    clipping = "unavailable"
    if geometry is not None and len(geometry) == 4:
        area_ratio = round(max(0.0, geometry[2] - geometry[0]) * max(0.0, geometry[3] - geometry[1]), 8)
        pixel_area = round(area_ratio * width * height) if isinstance(width, int) and isinstance(height, int) else None
        clipped = min(geometry) <= 0.01 or geometry[2] >= 0.99 or geometry[3] >= 0.99
        large_subject = area_ratio >= LARGE_SUBJECT_AREA_RATIO_FLOOR
        containment = "contained" if not clipped else "clipped"
        clipping = "edge_clipped" if clipped else "not_clipped"
        if clipped:
            # A large subject's edge contact is graded down, not excluded --
            # see LARGE_SUBJECT_AREA_RATIO_FLOOR above. Only a small,
            # edge-clipped box (the usual signature of a poor partial view)
            # remains a hard rejection, unchanged from before.
            reasons.add("subject_edge_clipped_large_subject" if large_subject else "subject_edge_clipped")
            components["containment"] = -10 if large_subject else -30
        else:
            reasons.add("subject_contained")
            components["containment"] = 20
        if area_ratio < 0.001 or (pixel_area is not None and pixel_area < 256):
            reasons.add("subject_too_small")
            components["subject_detail"] = -15
        else:
            components["subject_detail"] = min(20, max(2, int((pixel_area or 0) ** 0.5 / 8)))
    else:
        limitations.add("subject_geometry_unavailable")

    track_supported = bool(
        facts.get("track_supported") is True
        or candidate.track_generation_id
        or candidate.tracker_provenance
    )
    if track_supported:
        reasons.add("track_supported")
        components["track_support"] = 16
        if candidate.role in {"tracked_best", "final_supported", "detector_confirmed"}:
            reasons.add("tracked_frame_continuity")
            components["track_continuity"] = 8
    else:
        limitations.add("track_support_unavailable")

    temporal = str(facts.get("temporal_alignment") or "uncertain")
    if temporal in {"aligned", "supported", "same_frame"} or facts.get("track_active_at_capture") is True:
        temporal = "aligned"
        reasons.add("temporally_aligned")
        components["temporal"] = 18
    elif temporal in {"late", "stale", "outside_track"}:
        temporal = "rejected"
        components["temporal"] = -30
    else:
        temporal = "uncertain"
        reasons.add("temporal_alignment_uncertain")
        limitations.add("temporal_alignment_uncertain")
        components["temporal"] = 0

    if candidate.role == "high_resolution_burst" and (
        facts.get("subject_visible") is False
        or facts.get("subject_supported") is False
        or temporal == "rejected"
    ):
        reasons.add("burst_subject_unverified")
    if facts.get("subject_visible") is False or facts.get("subject_absent") is True:
        reasons.add("subject_absent")
    if facts.get("privacy_masked") is True or facts.get("analysis_excluded") is True:
        reasons.add("privacy_masked")

    sharpness = str(facts.get("sharpness") or "")
    exposure = None
    if image is not None:
        measured_sharpness, exposure = _image_quality(image)
        if not sharpness:
            sharpness = measured_sharpness
    if not sharpness:
        sharpness = "uncertain"
        limitations.add("sharpness_unavailable")
    if sharpness == "blurred":
        reasons.add("image_blurred")
        components["sharpness"] = -22
    elif sharpness == "sharp":
        components["sharpness"] = 20
    elif sharpness == "usable":
        components["sharpness"] = 10
    else:
        components["sharpness"] = 0
    if exposure == "underexposed" or facts.get("underexposed") is True:
        reasons.add("image_underexposed")
        components["exposure"] = -14
    elif exposure == "overexposed" or facts.get("overexposed") is True:
        reasons.add("image_overexposed")
        components["exposure"] = -14
    else:
        components["exposure"] = 4 if image is not None else 0
    if candidate.role == "high_resolution_burst" and pixel_area is not None and pixel_area >= 100_000:
        reasons.add("high_resolution_detail")
        components["high_resolution_detail"] = 15

    support_facts = tuple(sorted(
        (key, value) for key, value in facts.items()
        if key in {
            "track_supported", "detector_support", "tracker_support",
            "supporting_frame_count", "track_active_at_capture", "request_to_capture_ms",
        }
    ))
    identification = sum(components.values()) + _IDENTIFICATION_ROLE.get(candidate.role, 8)
    context = (
        _CONTEXT_ROLE.get(candidate.role, 8)
        + components.get("sharpness", 0)
        + components.get("exposure", 0)
        + max(0, components.get("temporal", 0) // 3)
        + max(0, components.get("track_support", 0) // 4)
    )
    eligible = not (_HARD_REJECTIONS & reasons) and "subject_too_small" not in reasons
    return EvidenceCandidateScore(
        candidate.media_asset_id, candidate.role, candidate.frame_id, candidate.captured_at,
        width if isinstance(width, int) else None, height if isinstance(height, int) else None,
        geometry, temporal, containment, clipping, sharpness, area_ratio, pixel_area,
        support_facts, tuple(sorted(components.items())), identification, context, eligible,
        tuple(sorted(reasons)), tuple(sorted(limitations)),
    )


def _best(scores: tuple[EvidenceCandidateScore, ...], *, context: bool) -> str | None:
    eligible = [item for item in scores if item.eligible]
    if not eligible:
        return None
    ranked = sorted(
        eligible,
        key=lambda item: (
            -(item.context_score if context else item.identification_score),
            item.candidate_id,
        ),
    )
    return ranked[0].candidate_id


def _candidate_order(candidate: EvidenceCandidate) -> tuple[int, str, str, str]:
    return (
        _candidate_offset(candidate), candidate.role, candidate.frame_id or "", candidate.media_asset_id,
    )


def _candidate_selection_order(
    candidate: EvidenceCandidate, media: Mapping[str, bytes | str | Path],
) -> tuple[int, int, str, str, str]:
    """Sustained-Activity Visit Admission Starvation & Stop-Finalization
    Correctness v1 (see "Bounded component decision horizon" in
    docs/tracklet-visit-assembly-contract.md): `score_proposal_evidence`
    truncates its own candidate pool to `EvidenceScoringBounds.
    max_candidates` (16) *before* ranking which is "best" -- for a
    long-lived proposal with far more retained evidence-candidate facts
    than that (a real, previously-unreachable shape a bounded forced
    decision can now legitimately produce), the plain offset-first order
    `_candidate_order` alone provides always prefers the *earliest*
    candidates -- for a proposal old enough to be force-decided, these are
    also the ones most likely to have already rotated out of the caller's
    own bounded, insertion-order evidence-byte cache (`engine_runtime.
    _harvest_burst_bytes`/`_harvest_same_frame_bytes`), even when plenty of
    later, still-available evidence exists in the very same proposal.
    Reproduced directly, deterministically, before this fix: a
    forced-decision winner with real, byte-backed evidence for 115 of its
    own 240 constituent generations still reached `blocked_missing_
    evidence`, because all 16 candidates the truncation kept were from its
    own oldest, already-evicted generations.

    Fixed narrowly, at candidate *selection priority* only -- never a
    bound/cache-size change (see docs/candidate-visit-authority-contract.md
    "Evidence-cache capacity" for why this milestone deliberately does not
    touch that): a candidate with real, retrievable bytes in `media` is now
    preferred over one without, before falling back to the original,
    unmodified `_candidate_order` as the tiebreak. A complete no-op
    whenever every candidate's bytes are available -- the overwhelming
    common case, every existing, already-validated short-Visit scenario:
    the new leading `0`/`1` term is then constant across every candidate,
    so the original order alone still decides, byte-for-byte identical to
    before this fix."""

    has_bytes = _media_bytes(media.get(candidate.media_asset_id)) is not None
    return (0 if has_bytes else 1, *_candidate_order(candidate))


def _candidate_offset(candidate: EvidenceCandidate) -> int:
    return candidate.source_offset_ms if candidate.source_offset_ms is not None else 2**63


def _media_bytes(value: bytes | str | Path | None) -> bytes | None:
    if isinstance(value, bytes):
        return value
    if isinstance(value, (str, Path)):
        try:
            return Path(value).read_bytes()
        except OSError:
            return None
    return None


def _decode(value: bytes) -> Image.Image | None:
    try:
        with Image.open(BytesIO(value)) as source:
            source.verify()
        with Image.open(BytesIO(value)) as source:
            return source.convert("L")
    except Exception:
        return None


def _image_quality(image: Image.Image) -> tuple[str, str]:
    sample = image.copy()
    sample.thumbnail((512, 512))
    edge_rms = ImageStat.Stat(sample.filter(ImageFilter.FIND_EDGES)).rms[0]
    sharpness = "blurred" if edge_rms < 6 else "sharp" if edge_rms >= 20 else "usable"
    mean = ImageStat.Stat(sample).mean[0]
    exposure = "underexposed" if mean < 20 else "overexposed" if mean > 235 else "usable"
    return sharpness, exposure
