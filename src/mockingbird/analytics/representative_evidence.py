"""Gate C -- Representative Species Evidence v1: pure, deterministic
selection of the single best already-persisted evidence image to represent
one reviewed taxon (see docs/representative-species-evidence-contract.md).

This module never queries a database, never decodes an image, and never
re-derives reviewed truth. It ranks an already-bounded, already-truth-
filtered list of per-Visit evidence facts -- exactly the same shape of
boundary `mockingbird.analytics.place_activity_report`/`historical_baseline`/
`place_change_summary` already establish: the repository resolves truth and
evidence facts, this module only ranks them.

## Why "effective primary status" is not a ranking field here

Every `EvidenceCandidateFact` this module ever sees already *is* one Visit's
own resolved primary/effective evidence frame (`StreamVisitSummary.
primary_evidence`) -- the same already-computed, already-tested pick the
Evidence Gallery, Bird Log, and Wildlife Insights all already reuse. Tier 1
of the evidence contract ("valid effective primary evidence") is therefore
satisfied by construction before a candidate ever reaches this module, not
by a field compared here. This module's own job is narrower and genuinely
new: deciding *which Visit's* already-resolved evidence best represents a
taxon when more than one confirmed Visit qualifies.

## Why sharpness/exposure are not ranking fields here

`mockingbird.observation.evidence_scoring` already computes sharpness/
exposure once, at capture time, to help choose each Visit's own primary
frame -- but does not persist that score per asset (`creates_truth=false`
shadow evidence, see docs/multi-frame-evidence-scoring-contract.md).
Recomputing it here would mean decoding image bytes during report
computation, which every caller of this module is required not to do (see
"Performance" in docs/representative-species-evidence-contract.md). A
persisted `is_primary` frame has already passed containment/edge-clipping
checks upstream (`select_effective_primary`/`evidence_scoring`'s own
rejection reasons) before it could ever become primary, so this module does
not re-derive that either.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence


@dataclass(frozen=True)
class EvidenceCandidateFact:
    """One Visit's already-resolved primary evidence, reduced to exactly
    the facts `select_representative_evidence` ranks by. `visit_id`/
    `media_asset_id` are carried through only as stable identity -- this
    module never uses them for anything but the final deterministic
    tie-break and as a handle the caller uses to look up the real evidence
    object it already has in hand.
    """

    visit_id: str
    media_asset_id: str
    captured_at: datetime
    # True only when this asset's own persisted `GeometryAttribution.
    # resolution_provenance == "synchronized"` -- a genuinely separate,
    # higher-resolution capture with *proven* field-of-view alignment (see
    # docs/source-resolution-multi-frame-species-evidence-contract.md).
    # Never inferred from pixel counts alone: a bigger image with no proven
    # provenance ranks on `asset_pixel_area` below, never on this flag.
    is_native_resolution: bool
    # True when a subject-relative region (a track box or a curated crop)
    # is resolved for this frame -- a subject-focused image outranks a raw,
    # uncropped full scene of the same taxon, all else equal.
    has_subject_region: bool
    # Pixel area of the resolved subject region, when `has_subject_region`;
    # 0 otherwise. Never claims a subject is bigger than it visibly is --
    # a plain, honest `width * height` of the region already resolved
    # upstream (this module does no geometry math itself).
    subject_pixel_area: int
    # Pixel area of the full evidence asset -- the weakest, last-resort
    # size signal, used only once native-resolution/subject-region/subject-
    # size are tied.
    asset_pixel_area: int


# A derived crop whose own short side is below this is an upscaled stub, not a
# legitimate subject-centred image: it earns no subject-region credit and
# competes on its raw pixel size like any other frame.
MIN_CROP_SHORT_SIDE_PX = 64


def _valid_normalized_box(box: Sequence[float] | None) -> tuple[float, float, float, float] | None:
    """A box only counts when it is four finite fractions describing a
    non-empty region inside the image -- never guess at a malformed one."""

    if box is None or len(box) != 4:
        return None
    left, top, right, bottom = (float(value) for value in box)
    if not all(0.0 <= value <= 1.0 for value in (left, top, right, bottom)):
        return None
    if right <= left or bottom <= top:
        return None
    return left, top, right, bottom


def resolve_subject_region(
    *,
    width: int | None,
    height: int | None,
    normalized_track_box: Sequence[float] | None,
    normalized_crop_box: Sequence[float] | None,
) -> tuple[bool, int]:
    """`(has_subject_region, subject_pixel_area)` for one evidence frame,
    in this frame's *own* pixels.

    Two different boxes arrive on a `VisitEvidenceFrame`, and they are in
    different coordinate spaces:

    - `normalized_track_box` is only ever populated for a frame that still
      spans the camera's full field of view with proven alignment (see
      `_frame_local_subject_box`), so it is a fraction of *this* image: the
      subject occupies `box * (width, height)` pixels of it.
    - `normalized_crop_box` is present on a *derived crop* and says where
      that crop sits in its parent frame. The crop image itself is already
      the subject-centred region, so its subject area is its own pixel area.
      Scaling the asset's dimensions by that parent-relative fraction (the
      earlier behaviour) shrank a good crop's area twice over and let a wide
      frame with a tiny speck outrank a clean, subject-centred crop.

    A crop below `MIN_CROP_SHORT_SIDE_PX` earns no region credit. Nothing
    here invents a subject: with no valid box, or unknown pixel size, the
    answer is `(False, 0)`.
    """

    if not width or not height:
        return False, 0
    track = _valid_normalized_box(normalized_track_box)
    if track is not None:
        left, top, right, bottom = track
        return True, round((right - left) * width) * round((bottom - top) * height)
    if _valid_normalized_box(normalized_crop_box) is not None and min(width, height) >= MIN_CROP_SHORT_SIDE_PX:
        return True, width * height
    return False, 0


def select_representative_evidence(
    candidates: Sequence[EvidenceCandidateFact],
) -> EvidenceCandidateFact | None:
    """Pick the single best candidate from an already-bounded, already
    truth-filtered pool for one taxon.

    Deterministic total order, most-preferred first:

    1. genuine, proven native/source resolution (`is_native_resolution`);
    2. a resolved subject region over a raw full frame (`has_subject_
       region`) -- the closest cheaply-available proxy for "crop
       completeness" this module has, since containment/edge-clipping were
       already enforced upstream when a frame became primary (see module
       docstring);
    3. subject pixel size (`subject_pixel_area`);
    4. overall asset pixel size (`asset_pixel_area`);
    5. capture recency (`captured_at`) -- a real but low-priority signal,
       deliberately below every quality dimension above;
    6. `visit_id`/`media_asset_id` -- a stable, arbitrary but fully
       deterministic final tie-break, so the result never depends on
       database retrieval order.

    Returns `None` for an empty candidate list -- "no safe representative
    evidence" is always a valid outcome (see "No-image semantics" in
    docs/representative-species-evidence-contract.md), never an error.
    """

    best: EvidenceCandidateFact | None = None
    best_key: tuple[bool, bool, int, int, datetime, str, str] | None = None
    for candidate in candidates:
        key = (
            candidate.is_native_resolution,
            candidate.has_subject_region,
            candidate.subject_pixel_area,
            candidate.asset_pixel_area,
            candidate.captured_at,
            candidate.visit_id,
            candidate.media_asset_id,
        )
        if best_key is None or key > best_key:
            best, best_key = candidate, key
    return best
