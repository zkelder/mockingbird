"""Deterministic, offline evidence-quality benchmark (Observation Engine v2
Stage 6.13).

This module is pure: no filesystem I/O, no network, no CUDA/ONNX Runtime/
OpenCV, no product-repository or product-database import (see
`evidence_benchmark_io.py`/`evidence_benchmark_cli.py` for the I/O and CLI
layers). It closes a standalone tooling gap Stage 6.7/6.10 acceptance work
repeatedly disclosed: evidence usefulness was reported with bounded
descriptive analysis instead of the same deterministic benchmark/report
machinery already established for detector, tracker, multi-scale, and burst
evaluation.

Hard architectural rule: this module CALLS the existing evidence scorer
(`mockingbird.observation.evidence_scoring.score_proposal_evidence`) for
every episode it evaluates. It owns only reviewed-truth ingestion, matching
candidates to annotations, metric calculation, comparison, and deterministic
reporting -- it never ranks or selects a "best" candidate itself, and never
reimplements scoring rules.

A "reviewed evidence candidate" is the smallest additive, versioned unit of
truth this module accepts. Its field set deliberately mirrors Stage 6.6
temporal-review annotation fields (`EvidenceUsefulness`, `BoxAnnotation`,
`Provenance` in `temporal_annotation.py`) rather than inventing new
vocabulary; `build_reviewed_evidence_manifest_from_temporal_review` derives
it mechanically from an already-loaded Stage 6.6/6.8 review packet so a
caller never has to hand-copy data that already exists in the reviewed
packet. See docs/evidence-benchmark-contract.md.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from typing import Callable, Literal, Mapping, Sequence

from mockingbird.observation.contracts import EvidenceCandidate, VisitProposal
from mockingbird.observation.evidence_scoring import (
    EVIDENCE_SCORING_VERSION,
    EvidenceScoringBounds,
    EvidenceSelection,
    score_proposal_evidence,
)
from mockingbird.observation.replay import semantic_fingerprint
from mockingbird.observation.temporal_annotation import AnnotationSet
from mockingbird.observation.temporal_capture import TRIGGER_POST_TRIGGER_CONTEXT, TRIGGER_PRETRIGGER_CONTEXT

REVIEWED_EVIDENCE_MANIFEST_VERSION = 1
EVIDENCE_BENCHMARK_REPORT_SCHEMA_VERSION = 1
EVIDENCE_BENCHMARK_VERSION = "evidence-quality-benchmark-v1"

STATE_EVALUATED = "evaluated"
STATE_NOT_EVALUATED = "not_evaluated"
STATE_INSUFFICIENT_TRUTH = "insufficient_truth"
STATE_UNSUPPORTED = "unsupported"
METRIC_STATES: tuple[str, ...] = (STATE_EVALUATED, STATE_NOT_EVALUATED, STATE_INSUFFICIENT_TRUTH, STATE_UNSUPPORTED)

_VALID_VISIBLE = (None, "yes", "no", "ambiguous")
_VALID_TEMPORAL = (None, "aligned", "uncertain", "rejected")
# The scorer's own declared-fact vocabulary (evidence_scoring.py's `_score`)
# differs from this module's reviewer-facing three-value vocabulary, which
# instead mirrors `EvidenceCandidateScore.temporal_status`'s *output* names
# for readability. Translate at the boundary rather than exposing the
# scorer's internal input spelling to reviewed-manifest authors.
_TEMPORAL_ALIGNMENT_TO_DECLARED_FACT = {"aligned": "aligned", "uncertain": "uncertain", "rejected": "late"}


class EvidenceBenchmarkError(ValueError):
    """A bounded evidence-benchmark validation or execution failure code."""


def _metric(value: object, state: str) -> dict[str, object]:
    if state not in METRIC_STATES:
        raise EvidenceBenchmarkError("invalid_metric_state")
    return {"state": state, "value": value if state == STATE_EVALUATED else None}


# --------------------------------------------------------------------------
# Reviewed evidence manifest -- the smallest additive versioned truth input.
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ReviewedEvidenceCandidate:
    """One reviewed candidate. Every field beyond identity/role is optional
    and additive; a caller supplies only what the source annotation actually
    supports. Fields split into two groups:

    - reconstruction facts (role, dimensions, geometry, timing, declared
      temporal_alignment/sharpness/decodable/privacy_masked) feed the
      existing scorer as `EvidenceCandidate.quality_facts`, the same way a
      live provider's own declared facts would;
    - reviewed truth (usefulness, preferred selection, blur/clip/occlusion/
      containment judgments, subject visibility) is never fed to the scorer
      and exists only to check the scorer's own output honestly.
    """

    candidate_id: str
    session_id: str
    role: str
    track_generation_id: str | None = None
    episode_id: str | None = None
    width: int | None = None
    height: int | None = None
    subject_geometry: tuple[float, float, float, float] | None = None
    source_offset_ms: int | None = None
    captured_at_iso: str | None = None
    high_resolution: bool = False
    # The reviewed source frame's own content hash, when recorded (Stage
    # 6.6/6.8 `RetainedFrameRecord.content_hash`) -- used only for the
    # Stage 6.14 source-lineage collision/integrity check against a
    # replay-sourced candidate's own `source_content_hash`, never fed to the
    # scorer. See docs/reviewed-replay-lineage-contract.md.
    content_hash: str | None = None
    request_to_capture_ms: float | None = None
    temporal_alignment: str | None = None
    timing_uncertainty_ms: int | None = None
    privacy_masked: bool | None = None
    decodable: bool | None = None
    sharpness: str | None = None
    image_path: str | None = None

    reviewed_subject_visible: str | None = None
    ambiguous: bool = False
    useful_broad_confirmation: bool | None = None
    useful_identification: bool | None = None
    useful_context: bool | None = None
    preferred_identification: bool | None = None
    preferred_context: bool | None = None
    reviewed_blurred: bool | None = None
    reviewed_clipped: bool | None = None
    reviewed_occluded: bool | None = None
    reviewed_subject_contained: bool | None = None
    reviewer: str | None = None
    reviewed_at_iso: str | None = None
    truth_source: str | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.session_id or not self.role:
            raise EvidenceBenchmarkError("invalid_reviewed_candidate_identity")
        if self.reviewed_subject_visible not in _VALID_VISIBLE:
            raise EvidenceBenchmarkError("invalid_reviewed_subject_visible")
        if self.temporal_alignment not in _VALID_TEMPORAL:
            raise EvidenceBenchmarkError("invalid_temporal_alignment")
        if self.subject_geometry is not None and len(self.subject_geometry) != 4:
            raise EvidenceBenchmarkError("invalid_subject_geometry")

    @property
    def episode_key(self) -> str:
        return self.episode_id or f"{self.session_id}:{self.track_generation_id or 'context'}"


@dataclass(frozen=True)
class ReviewedAppearance:
    """A reviewed appearance span, mirroring `temporal_annotation.
    AppearanceInterval`/`replay.ExpectedAppearance` in spirit: the earliest
    genuine subject presence a benchmark can honestly measure evidence
    latency against."""

    appearance_id: str
    session_id: str
    start_offset_ms: int
    end_offset_ms: int

    def __post_init__(self) -> None:
        if not self.appearance_id or not self.session_id:
            raise EvidenceBenchmarkError("invalid_reviewed_appearance_identity")
        if self.start_offset_ms < 0 or self.end_offset_ms < self.start_offset_ms:
            raise EvidenceBenchmarkError("invalid_reviewed_appearance_span")


@dataclass(frozen=True)
class ReviewedEvidenceManifest:
    manifest_version: int
    manifest_id: str
    source_description: str
    candidates: tuple[ReviewedEvidenceCandidate, ...]
    appearances: tuple[ReviewedAppearance, ...] = ()

    def __post_init__(self) -> None:
        if self.manifest_version != REVIEWED_EVIDENCE_MANIFEST_VERSION:
            raise EvidenceBenchmarkError("unsupported_manifest_version")
        if not self.manifest_id:
            raise EvidenceBenchmarkError("invalid_manifest_id")
        if len(self.candidates) > 20_000 or len(self.appearances) > 2_000:
            raise EvidenceBenchmarkError("manifest_limit")
        ids = [item.candidate_id for item in self.candidates]
        if len(ids) != len(set(ids)):
            raise EvidenceBenchmarkError("duplicate_candidate_id")
        appearance_ids = [item.appearance_id for item in self.appearances]
        if len(appearance_ids) != len(set(appearance_ids)):
            raise EvidenceBenchmarkError("duplicate_appearance_id")

    def _ordered_candidates(self) -> list[dict[str, object]]:
        # Candidate order carries no semantic meaning of its own (unlike a
        # frame sequence's temporal order) -- canonicalize by candidate_id so
        # the same logical reviewed set fingerprints identically regardless
        # of input list order, matching this module's report-wide
        # deterministic-ordering guarantee.
        return [asdict(item) for item in sorted(self.candidates, key=lambda item: item.candidate_id)]

    def _ordered_appearances(self) -> list[dict[str, object]]:
        return [asdict(item) for item in sorted(self.appearances, key=lambda item: item.appearance_id)]

    @property
    def fingerprint(self) -> str:
        return semantic_fingerprint({
            "manifest_version": self.manifest_version,
            "manifest_id": self.manifest_id,
            "source_description": self.source_description,
            "candidates": self._ordered_candidates(),
            "appearances": self._ordered_appearances(),
        })

    def to_semantic_dict(self) -> dict[str, object]:
        return {
            "manifest_version": self.manifest_version,
            "manifest_id": self.manifest_id,
            "source_description": self.source_description,
            "candidates": self._ordered_candidates(),
            "appearances": self._ordered_appearances(),
            "fingerprint": self.fingerprint,
        }


# --------------------------------------------------------------------------
# Episode reconstruction and scoring (reuses evidence_scoring.py unchanged)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EpisodeResult:
    episode_id: str
    session_id: str
    track_generation_id: str | None
    proposal_key: str
    manifest_candidate_ids: tuple[str, ...]
    selection: EvidenceSelection
    source: Literal["reviewed_manifest", "replay_report"]
    # Stage 6.14: the scorer's own selected candidate identity
    # (`selection.identification_candidate_id`/`context_candidate_id`,
    # unchanged) translated into the reviewed original capture-frame
    # identity it provably traces back to, via
    # `EvidenceCandidate.source_capture_frame_id` -- `None` when no source
    # lineage is known (an old replay report, a non-temporal-review replay
    # input, or a candidate whose lineage failed an integrity check). See
    # docs/reviewed-replay-lineage-contract.md.
    identification_source_capture_frame_id: str | None = None
    context_source_capture_frame_id: str | None = None


def _generation_from_episode_key(episode_key: str, session_id: str) -> str | None:
    prefix = f"{session_id}:"
    if not episode_key.startswith(prefix):
        return None
    suffix = episode_key[len(prefix):]
    return None if suffix == "context" else suffix


def _quality_facts_for(item: ReviewedEvidenceCandidate) -> tuple[tuple[str, object], ...]:
    facts: list[tuple[str, object]] = []
    if item.decodable is not None:
        facts.append(("decodable", item.decodable))
    if item.temporal_alignment is not None:
        facts.append(("temporal_alignment", _TEMPORAL_ALIGNMENT_TO_DECLARED_FACT[item.temporal_alignment]))
    if item.privacy_masked is not None:
        facts.append(("privacy_masked", item.privacy_masked))
    if item.sharpness is not None:
        facts.append(("sharpness", item.sharpness))
    if item.request_to_capture_ms is not None:
        facts.append(("request_to_capture_ms", item.request_to_capture_ms))
    if item.reviewed_subject_visible == "no":
        facts.append(("subject_visible", False))
    return tuple(facts)


def _to_evidence_candidate(item: ReviewedEvidenceCandidate) -> EvidenceCandidate:
    return EvidenceCandidate(
        media_asset_id=item.candidate_id,
        stream_id=item.session_id,
        role=item.role,
        captured_at=None,
        frame_id=item.candidate_id,
        source_offset_ms=item.source_offset_ms,
        width=item.width,
        height=item.height,
        subject_geometry=item.subject_geometry,
        track_generation_id=item.track_generation_id,
        quality_facts=_quality_facts_for(item),
        # A reviewed-manifest-derived candidate's own identity already *is*
        # the original reviewed frame's identity by construction -- see
        # docs/reviewed-replay-lineage-contract.md. Setting these explicitly
        # (rather than leaving them unset) lets every downstream join use
        # the same "prefer source_capture_frame_id" rule uniformly for both
        # a reviewed-manifest-derived and a replay-sourced candidate.
        source_capture_frame_id=item.candidate_id,
        source_content_hash=item.content_hash,
    )


def _source_lineage_join(
    manifest: ReviewedEvidenceManifest,
    replay_candidates: tuple[EvidenceCandidate, ...],
) -> tuple[dict[str, str], tuple[str, ...]]:
    """Resolve every candidate's scorer-space identity (`media_asset_id`,
    what `EvidenceSelection.identification_candidate_id`/`context_candidate_id`
    actually carry) to the reviewed original capture-frame identity it
    provably traces back to -- the preferred join key -- honestly refusing
    an ambiguous or conflicting case rather than silently choosing one. See
    docs/reviewed-replay-lineage-contract.md, "Collision/integrity
    handling". A reviewed-manifest-derived candidate's join is trivial (its
    own identity already *is* the reviewed identity by construction, see
    `_to_evidence_candidate`); a replay-sourced candidate's join depends on
    its own additive `source_capture_frame_id`/`source_content_hash`
    provenance, present only once threaded all the way through a Stage
    6.14-aware replay."""

    limitations: list[str] = []
    truth_by_id = {item.candidate_id: item for item in manifest.candidates}
    join_map: dict[str, str] = {item.candidate_id: item.candidate_id for item in manifest.candidates}

    # One reviewed source identity must map to exactly one content hash
    # across every replay-sourced candidate that declares one; two replay
    # candidates disagreeing about "what frame this reviewed identity
    # actually was" is never safe to resolve by picking either side.
    hashes_by_source_id: dict[str, set[str]] = {}
    for candidate in replay_candidates:
        source_id = candidate.source_capture_frame_id
        if source_id and candidate.source_content_hash:
            hashes_by_source_id.setdefault(source_id, set()).add(candidate.source_content_hash)
    conflicting_source_ids = {source_id for source_id, hashes in hashes_by_source_id.items() if len(hashes) > 1}
    if conflicting_source_ids:
        limitations.append(
            "duplicate_source_identity_conflicting_content: replay-sourced candidates disagree about the "
            "content hash of reviewed source frame(s) " + ",".join(sorted(conflicting_source_ids))
        )

    any_source_lineage = False
    unknown_source_ids: set[str] = set()
    mismatched_source_ids: set[str] = set()
    for candidate in sorted(replay_candidates, key=lambda item: item.media_asset_id):
        source_id = candidate.source_capture_frame_id
        if not source_id:
            continue
        any_source_lineage = True
        if source_id in conflicting_source_ids:
            continue
        truth = truth_by_id.get(source_id)
        if truth is None:
            unknown_source_ids.add(source_id)
            continue
        if candidate.source_content_hash and truth.content_hash and candidate.source_content_hash != truth.content_hash:
            mismatched_source_ids.add(source_id)
            continue
        join_map[candidate.media_asset_id] = source_id

    if unknown_source_ids:
        limitations.append(
            "unknown_reviewed_source_frame: replay evidence references reviewed source frame(s) "
            + ",".join(sorted(unknown_source_ids)) + " not present in the reviewed manifest"
        )
    if mismatched_source_ids:
        limitations.append(
            "source_hash_mismatch: reviewed and replay content hashes disagree for reviewed source frame(s) "
            + ",".join(sorted(mismatched_source_ids))
        )
    if replay_candidates and not any_source_lineage:
        limitations.append(
            "source_lineage_unavailable: no replay-sourced candidate carries a source_capture_frame_id; "
            "either this replay report predates Stage 6.14 or its input was not derived from reviewed "
            "temporal-review capture data (see docs/reviewed-replay-lineage-contract.md)"
        )
    return join_map, tuple(limitations)


def _join(join_map: Mapping[str, str], candidate_id: str | None) -> str | None:
    return join_map.get(candidate_id) if candidate_id is not None else None


def _media_with_source_lineage_fallback(
    media: Mapping[str, object] | None,
    replay_candidates: tuple[EvidenceCandidate, ...],
    join_map: Mapping[str, str],
) -> Mapping[str, object] | None:
    """A replay-sourced `EvidenceCandidate`'s own `media_asset_id`
    (replay-local, e.g. `"replay:17"`) is never a key a caller's `media`
    mapping (built from the *reviewed* frame root, keyed by reviewed
    `candidate_id`) can already contain -- without this, every
    replay-sourced candidate's own rescoring call would see no image bytes
    at all and score `candidate_unavailable` regardless of lineage,
    silently defeating the whole point of joining it to reviewed truth.
    This extends `media` so a replay-sourced candidate can decode the exact
    same bytes a reviewer looked at, using only a source identity
    `_source_lineage_join` already verified safe (never a raw, unverified
    `EvidenceCandidate.source_capture_frame_id` -- a hash mismatch or
    conflicting-content case must not silently borrow reviewed image bytes
    either). A caller-supplied entry already keyed by the candidate's own
    `media_asset_id` is never overwritten; `media` is returned unchanged
    when there is nothing to add."""

    if not media:
        return media
    extended: dict[str, object] | None = None
    for candidate in replay_candidates:
        if candidate.media_asset_id in media:
            continue
        source_id = join_map.get(candidate.media_asset_id)
        source_media = media.get(source_id) if source_id is not None else None
        if source_media is None:
            continue
        if extended is None:
            extended = dict(media)
        extended.setdefault(candidate.media_asset_id, source_media)
    return extended if extended is not None else media


def _build_manifest_episodes(
    manifest: ReviewedEvidenceManifest,
    media: Mapping[str, object] | None,
    bounds: EvidenceScoringBounds | None,
    join_map: Mapping[str, str],
) -> tuple[EpisodeResult, ...]:
    groups: dict[str, list[ReviewedEvidenceCandidate]] = {}
    for item in sorted(manifest.candidates, key=lambda item: item.candidate_id):
        groups.setdefault(item.episode_key, []).append(item)
    results: list[EpisodeResult] = []
    for episode_id in sorted(groups):
        items = groups[episode_id]
        session_id = items[0].session_id
        generation = _generation_from_episode_key(episode_id, session_id)
        candidates = tuple(_to_evidence_candidate(item) for item in items)
        proposal = VisitProposal(
            proposal_key=f"evidence-benchmark:{episode_id}",
            source_id=session_id,
            stream_id=session_id,
            evidence_media_asset_ids=tuple(item.candidate_id for item in items),
            reason="reviewed_evidence_episode",
            track_generation_id=generation,
        )
        selection = score_proposal_evidence(proposal, candidates, media=media, bounds=bounds)
        results.append(EpisodeResult(
            episode_id, session_id, generation, proposal.proposal_key,
            tuple(item.candidate_id for item in items), selection, "reviewed_manifest",
            _join(join_map, selection.identification_candidate_id),
            _join(join_map, selection.context_candidate_id),
        ))
    return tuple(results)


def _build_replay_episodes(
    replay_candidates: tuple[EvidenceCandidate, ...],
    replay_proposals: tuple[VisitProposal, ...],
    media: Mapping[str, object] | None,
    bounds: EvidenceScoringBounds | None,
    join_map: Mapping[str, str],
) -> tuple[EpisodeResult, ...]:
    results: list[EpisodeResult] = []
    for proposal in sorted(replay_proposals, key=lambda item: item.proposal_key):
        selection = score_proposal_evidence(proposal, replay_candidates, media=media, bounds=bounds)
        episode_id = f"replay-report:{proposal.proposal_key}"
        results.append(EpisodeResult(
            episode_id, proposal.source_id, proposal.track_generation_id, proposal.proposal_key,
            proposal.evidence_media_asset_ids, selection, "replay_report",
            _join(join_map, selection.identification_candidate_id),
            _join(join_map, selection.context_candidate_id),
        ))
    return tuple(results)


# --------------------------------------------------------------------------
# Metric computation helpers
# --------------------------------------------------------------------------


def _domain(
    candidates: Sequence[ReviewedEvidenceCandidate], has_value: Callable[[ReviewedEvidenceCandidate], bool],
) -> tuple[str, tuple[ReviewedEvidenceCandidate, ...]]:
    """Classify a truth field's domain the same way the established
    `replay._evidence_metrics` precedent does: not_evaluated when nobody
    ever set the field, insufficient_truth when every value that exists is
    marked ambiguous, evaluated (with only the non-ambiguous subset usable)
    otherwise."""

    domain = tuple(item for item in candidates if has_value(item))
    if not domain:
        return STATE_NOT_EVALUATED, ()
    usable = tuple(item for item in domain if not item.ambiguous)
    if not usable:
        return STATE_INSUFFICIENT_TRUTH, ()
    return STATE_EVALUATED, usable


def _count_metric(
    candidates: Sequence[ReviewedEvidenceCandidate],
    has_value: Callable[[ReviewedEvidenceCandidate], bool],
    is_true: Callable[[ReviewedEvidenceCandidate], bool],
) -> dict[str, object]:
    state, usable = _domain(candidates, has_value)
    if state != STATE_EVALUATED:
        return _metric(None, state)
    return _metric(sum(1 for item in usable if is_true(item)), STATE_EVALUATED)


def _selected_rate_metric(
    candidates: Sequence[ReviewedEvidenceCandidate],
    selected_ids: Sequence[str | None],
    has_value: Callable[[ReviewedEvidenceCandidate], bool],
    is_true: Callable[[ReviewedEvidenceCandidate], bool],
) -> dict[str, object]:
    """A rate restricted to the population the scorer actually selected,
    mirroring the existing `useful_primary_rate` precedent's own
    zero-denominator downgrade: truth genuinely absent is not_evaluated/
    insufficient_truth; truth present globally but nothing selected ties to
    it becomes insufficient_truth rather than a fabricated 0.0/1.0."""

    domain_state, _ = _domain(candidates, has_value)
    if domain_state != STATE_EVALUATED:
        return _metric(None, domain_state)
    by_id = {item.candidate_id: item for item in candidates if has_value(item) and not item.ambiguous}
    linked = [by_id[item] for item in selected_ids if item is not None and item in by_id]
    if not linked:
        return _metric(None, STATE_INSUFFICIENT_TRUTH)
    return _metric(sum(1 for item in linked if is_true(item)) / len(linked), STATE_EVALUATED)


def _scorer_rate_metric(scores: Sequence[object], is_true: Callable[[object], bool]) -> dict[str, object]:
    """A rate derived purely from the scorer's own output (no reviewed
    truth involved at all), so an empty population is a structural
    not_evaluated, never insufficient_truth."""

    if not scores:
        return _metric(None, STATE_NOT_EVALUATED)
    return _metric(sum(1 for item in scores if is_true(item)) / len(scores), STATE_EVALUATED)


def _role_distribution(scores: Sequence[object]) -> dict[str, object]:
    if not scores:
        return _metric(None, STATE_NOT_EVALUATED)
    counter = Counter(item.role for item in scores)
    return _metric(dict(sorted(counter.items())), STATE_EVALUATED)


def _selection_correctness_metric(
    episodes: Sequence[EpisodeResult],
    truth_by_episode: Mapping[str, tuple[ReviewedEvidenceCandidate, ...]],
    preferred_field: str,
    selected_source_id: Callable[[EpisodeResult], str | None],
) -> dict[str, object]:
    all_relevant = tuple(
        item for candidates in truth_by_episode.values() for item in candidates
        if getattr(item, preferred_field) is not None
    )
    domain_state, _ = _domain(all_relevant, lambda item: True)
    if domain_state != STATE_EVALUATED:
        return _metric(None, domain_state)
    judgements: list[bool] = []
    for episode in episodes:
        preferred_ids = {
            item.candidate_id for item in truth_by_episode.get(episode.episode_id, ())
            if getattr(item, preferred_field) is True and not item.ambiguous
        }
        if not preferred_ids:
            continue
        # Joined via each episode's own reviewed source-frame identity
        # (Stage 6.14), never the scorer's raw, replay-local candidate id --
        # see docs/reviewed-replay-lineage-contract.md.
        judgements.append(selected_source_id(episode) in preferred_ids)
    if not judgements:
        return _metric(None, STATE_INSUFFICIENT_TRUTH)
    return _metric(sum(judgements) / len(judgements), STATE_EVALUATED)


_ALL_METRIC_NAMES: tuple[str, ...] = (
    "episodes_evaluated", "episodes_with_any_evidence", "episodes_with_identification_candidate",
    "episodes_with_context_candidate", "episodes_with_alternates", "no_useful_evidence_count",
    "reviewed_useful_identification_candidate_count", "useful_identification_rate",
    "selected_identification_correctness", "identification_subject_contained_rate",
    "identification_clipped_rate", "identification_blurred_unusable_rate",
    "identification_high_resolution_selection_rate", "identification_analysis_frame_selection_rate",
    "reviewed_useful_context_candidate_count", "useful_context_rate", "selected_context_correctness",
    "context_subject_visible_rate", "context_role_distribution",
    "selected_evidence_temporal_alignment_rate", "selected_evidence_temporal_uncertain_rate",
    "evidence_latency_from_appearance_ms", "burst_request_to_capture_latency_ms",
    "temporal_uncertainty_ms_average", "stale_generation_rejection_count",
    "candidates_per_episode_mean", "eligible_candidates_count", "rejected_candidates_count",
    "rejection_reason_distribution", "selected_identification_role_distribution",
    "selected_context_role_distribution", "alternate_role_distribution",
    "candidates_presented_per_episode_mean", "episodes_with_no_useful_automatic_identification",
    "episodes_requiring_alternate_inspection",
)


def _compute_metrics(
    episodes: tuple[EpisodeResult, ...],
    manifest: ReviewedEvidenceManifest,
) -> dict[str, dict[str, object]]:
    all_candidates = manifest.candidates
    truth_by_episode: dict[str, tuple[ReviewedEvidenceCandidate, ...]] = {}
    for item in all_candidates:
        truth_by_episode.setdefault(item.episode_key, []).append(item)  # type: ignore[arg-type]
    truth_by_episode = {key: tuple(value) for key, value in truth_by_episode.items()}
    truth_by_id = {item.candidate_id: item for item in all_candidates}

    all_scores = [score for episode in episodes for score in episode.selection.candidate_scores]
    eligible_scores = [score for score in all_scores if score.eligible]
    ineligible_scores = [score for score in all_scores if not score.eligible]

    identification_ids = [episode.selection.identification_candidate_id for episode in episodes]
    context_ids = [episode.selection.context_candidate_id for episode in episodes]
    # Stage 6.14: the reviewed original capture-frame identity each
    # episode's own selection actually joins to, when known -- the
    # preferred join key for every truth-dependent metric below, kept
    # separate from `identification_ids`/`context_ids` above (which stay in
    # the scorer's own candidate-id space for purely structural counts that
    # need no truth join at all). See docs/reviewed-replay-lineage-contract.md.
    identification_join_ids = [episode.identification_source_capture_frame_id for episode in episodes]
    context_join_ids = [episode.context_source_capture_frame_id for episode in episodes]
    identification_scores = [
        episode.selection.score_for(episode.selection.identification_candidate_id)
        for episode in episodes if episode.selection.identification_candidate_id is not None
    ]
    context_scores = [
        episode.selection.score_for(episode.selection.context_candidate_id)
        for episode in episodes if episode.selection.context_candidate_id is not None
    ]
    selected_scores: list[object] = []
    for episode in episodes:
        seen: set[str] = set()
        for candidate_id in (episode.selection.identification_candidate_id, episode.selection.context_candidate_id):
            if candidate_id is not None and candidate_id not in seen:
                seen.add(candidate_id)
                selected_scores.append(episode.selection.score_for(candidate_id))

    appearance_starts_by_session: dict[str, list[int]] = {}
    for appearance in manifest.appearances:
        appearance_starts_by_session.setdefault(appearance.session_id, []).append(appearance.start_offset_ms)
    for starts in appearance_starts_by_session.values():
        starts.sort()

    metrics: dict[str, dict[str, object]] = {
        # Availability
        "episodes_evaluated": _metric(len(episodes), STATE_EVALUATED),
        "episodes_with_any_evidence": _metric(
            sum(1 for episode in episodes if episode.selection.candidate_scores), STATE_EVALUATED,
        ),
        "episodes_with_identification_candidate": _metric(
            sum(1 for item in identification_ids if item is not None), STATE_EVALUATED,
        ),
        "episodes_with_context_candidate": _metric(sum(1 for item in context_ids if item is not None), STATE_EVALUATED),
        "episodes_with_alternates": _metric(
            sum(1 for episode in episodes if episode.selection.alternate_candidate_ids), STATE_EVALUATED,
        ),
        "no_useful_evidence_count": _metric(
            sum(1 for episode in episodes if episode.selection.no_useful_evidence), STATE_EVALUATED,
        ),
        # Identification
        "reviewed_useful_identification_candidate_count": _count_metric(
            all_candidates, lambda item: item.useful_identification is not None,
            lambda item: item.useful_identification is True,
        ),
        "useful_identification_rate": _selected_rate_metric(
            all_candidates, identification_join_ids, lambda item: item.useful_identification is not None,
            lambda item: item.useful_identification is True,
        ),
        "selected_identification_correctness": _selection_correctness_metric(
            episodes, truth_by_episode, "preferred_identification",
            lambda episode: episode.identification_source_capture_frame_id,
        ),
        "identification_subject_contained_rate": _scorer_rate_metric(
            identification_scores, lambda score: score.containment_status == "contained",
        ),
        "identification_clipped_rate": _scorer_rate_metric(
            identification_scores, lambda score: score.edge_clipping_status == "edge_clipped",
        ),
        "identification_blurred_unusable_rate": _scorer_rate_metric(
            identification_scores, lambda score: score.sharpness_category == "blurred",
        ),
        "identification_high_resolution_selection_rate": _scorer_rate_metric(
            identification_scores, lambda score: score.role == "high_resolution_burst",
        ),
        "identification_analysis_frame_selection_rate": _scorer_rate_metric(
            identification_scores, lambda score: score.role != "high_resolution_burst",
        ),
        # Context
        "reviewed_useful_context_candidate_count": _count_metric(
            all_candidates, lambda item: item.useful_context is not None, lambda item: item.useful_context is True,
        ),
        "useful_context_rate": _selected_rate_metric(
            all_candidates, context_join_ids, lambda item: item.useful_context is not None,
            lambda item: item.useful_context is True,
        ),
        "selected_context_correctness": _selection_correctness_metric(
            episodes, truth_by_episode, "preferred_context",
            lambda episode: episode.context_source_capture_frame_id,
        ),
        "context_subject_visible_rate": _selected_rate_metric(
            all_candidates, context_join_ids, lambda item: item.reviewed_subject_visible is not None,
            lambda item: item.reviewed_subject_visible == "yes",
        ),
        "context_role_distribution": _role_distribution(context_scores),
        # Temporal
        "selected_evidence_temporal_alignment_rate": _scorer_rate_metric(
            selected_scores, lambda score: score.temporal_status == "aligned",
        ),
        "selected_evidence_temporal_uncertain_rate": _scorer_rate_metric(
            selected_scores, lambda score: score.temporal_status == "uncertain",
        ),
        "evidence_latency_from_appearance_ms": _evidence_latency_from_appearance(
            episodes, truth_by_id, appearance_starts_by_session, manifest,
        ),
        "burst_request_to_capture_latency_ms": _burst_latency(all_candidates),
        "temporal_uncertainty_ms_average": _timing_uncertainty_average(all_candidates),
        "stale_generation_rejection_count": _metric(
            sum(_stale_generation_count(episode, truth_by_episode) for episode in episodes), STATE_EVALUATED,
        ),
        # Candidate quality
        "candidates_per_episode_mean": _mean_metric([len(episode.selection.candidate_scores) for episode in episodes]),
        "eligible_candidates_count": _metric(len(eligible_scores), STATE_EVALUATED),
        "rejected_candidates_count": _metric(len(ineligible_scores), STATE_EVALUATED),
        "rejection_reason_distribution": _reason_distribution(ineligible_scores),
        "selected_identification_role_distribution": _role_distribution(identification_scores),
        "selected_context_role_distribution": _role_distribution(context_scores),
        "alternate_role_distribution": _role_distribution([
            episode.selection.score_for(candidate_id)
            for episode in episodes for candidate_id in episode.selection.alternate_candidate_ids
        ]),
        # Human-review workload proxy (deterministic structural facts only)
        "candidates_presented_per_episode_mean": _mean_metric([len(episode.selection.candidate_scores) for episode in episodes]),
        "episodes_with_no_useful_automatic_identification": _metric(
            sum(1 for item in identification_ids if item is None), STATE_EVALUATED,
        ),
        "episodes_requiring_alternate_inspection": _metric(
            sum(
                1 for episode in episodes
                if episode.selection.identification_candidate_id is None and episode.selection.alternate_candidate_ids
            ),
            STATE_EVALUATED,
        ),
    }
    assert set(metrics) == set(_ALL_METRIC_NAMES), "metric name drift between _ALL_METRIC_NAMES and _compute_metrics"
    return metrics


def _mean_metric(values: Sequence[int]) -> dict[str, object]:
    if not values:
        return _metric(None, STATE_NOT_EVALUATED)
    return _metric(sum(values) / len(values), STATE_EVALUATED)


def _reason_distribution(scores: Sequence[object]) -> dict[str, object]:
    if not scores:
        return _metric(None, STATE_NOT_EVALUATED)
    counter: Counter[str] = Counter()
    for score in scores:
        counter.update(score.reason_codes)
    return _metric(dict(sorted(counter.items())), STATE_EVALUATED)


def _stale_generation_count(
    episode: EpisodeResult, truth_by_episode: Mapping[str, tuple[ReviewedEvidenceCandidate, ...]],
) -> int:
    if episode.track_generation_id is None:
        return 0
    return sum(
        1 for item in truth_by_episode.get(episode.episode_id, ())
        if item.track_generation_id is not None and item.track_generation_id != episode.track_generation_id
    )


def _timing_uncertainty_average(candidates: Sequence[ReviewedEvidenceCandidate]) -> dict[str, object]:
    state, usable = _domain(candidates, lambda item: item.timing_uncertainty_ms is not None)
    if state != STATE_EVALUATED:
        return _metric(None, state)
    values = [item.timing_uncertainty_ms for item in usable]
    return _metric(sum(values) / len(values), STATE_EVALUATED)


def _burst_latency(candidates: Sequence[ReviewedEvidenceCandidate]) -> dict[str, object]:
    bursts = [item for item in candidates if item.role == "high_resolution_burst"]
    state, usable = _domain(bursts, lambda item: item.request_to_capture_ms is not None)
    if state != STATE_EVALUATED:
        return _metric(None, state)
    values = [item.request_to_capture_ms for item in usable]
    return _metric(sum(values) / len(values), STATE_EVALUATED)


def _nearest_appearance_start(starts: Sequence[int], offset: int) -> int:
    """The evidence's own most plausible reference point: the latest
    reviewed appearance that had already begun by the time this candidate
    was captured (a session can carry more than one reviewed appearance, so
    using the session's single earliest appearance for every episode would
    silently misattribute later episodes to the wrong appearance). Falls
    back to the session's earliest appearance for evidence captured before
    any known appearance (for example genuine pretrigger context)."""

    preceding = [start for start in starts if start <= offset]
    return max(preceding) if preceding else starts[0]


def _evidence_latency_from_appearance(
    episodes: Sequence[EpisodeResult],
    truth_by_id: Mapping[str, ReviewedEvidenceCandidate],
    appearance_starts_by_session: Mapping[str, list[int]],
    manifest: ReviewedEvidenceManifest,
) -> dict[str, object]:
    if not manifest.appearances:
        return _metric(None, STATE_NOT_EVALUATED)
    latencies: list[int] = []
    for episode in episodes:
        # Joined via the reviewed source-frame identity (Stage 6.14), which
        # also recovers the *real* reviewed session id from truth -- unlike
        # `episode.session_id`, which for a replay-sourced episode is the
        # replay provider's own run-mode label ("replay"/"live_shadow"), not
        # a reviewed session id `appearance_starts_by_session` is keyed by.
        source_id = episode.identification_source_capture_frame_id
        if source_id is None:
            continue
        truth = truth_by_id.get(source_id)
        if truth is None or truth.source_offset_ms is None:
            continue
        starts = appearance_starts_by_session.get(truth.session_id)
        if not starts:
            continue
        offset = truth.source_offset_ms
        latencies.append(offset - _nearest_appearance_start(starts, offset))
    if not latencies:
        return _metric(None, STATE_INSUFFICIENT_TRUTH)
    return _metric(sum(latencies) / len(latencies), STATE_EVALUATED)


# --------------------------------------------------------------------------
# Report
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceBenchmarkReport:
    schema_version: int
    manifest_fingerprint: str
    policy_identity: dict[str, object]
    provider_identity: dict[str, object] | None
    replay_report_fingerprint: str | None
    episodes: tuple[EpisodeResult, ...]
    evidence_candidates: tuple[EvidenceCandidate, ...]
    evidence_selections: tuple[EvidenceSelection, ...]
    evidence_fingerprint: str
    reviewed_manifest: dict[str, object]
    metrics: dict[str, dict[str, object]]
    limitations: tuple[str, ...]
    semantic_fingerprint: str

    def to_semantic_dict(self) -> dict[str, object]:
        return _semantic_payload(
            self.schema_version, self.manifest_fingerprint, self.policy_identity, self.provider_identity,
            self.replay_report_fingerprint, self.episodes, self.evidence_candidates, self.evidence_selections,
            self.evidence_fingerprint, self.reviewed_manifest, self.metrics, self.limitations,
        )


def _semantic_payload(
    schema_version: int,
    manifest_fingerprint: str,
    policy_identity: dict[str, object],
    provider_identity: dict[str, object] | None,
    replay_report_fingerprint: str | None,
    episodes: tuple[EpisodeResult, ...],
    evidence_candidates: tuple[EvidenceCandidate, ...],
    evidence_selections: tuple[EvidenceSelection, ...],
    evidence_fingerprint: str,
    reviewed_manifest: dict[str, object],
    metrics: dict[str, dict[str, object]],
    limitations: tuple[str, ...],
) -> dict[str, object]:
    return {
        "schema_version": schema_version,
        "benchmark_version": EVIDENCE_BENCHMARK_VERSION,
        "manifest_fingerprint": manifest_fingerprint,
        "policy_identity": policy_identity,
        "provider_identity": provider_identity,
        "replay_report_fingerprint": replay_report_fingerprint,
        "episodes": [
            {
                "episode_id": episode.episode_id,
                "session_id": episode.session_id,
                "track_generation_id": episode.track_generation_id,
                "proposal_key": episode.proposal_key,
                "manifest_candidate_ids": list(episode.manifest_candidate_ids),
                "source": episode.source,
                "selection": asdict(episode.selection),
                "identification_source_capture_frame_id": episode.identification_source_capture_frame_id,
                "context_source_capture_frame_id": episode.context_source_capture_frame_id,
            }
            for episode in episodes
        ],
        "evidence_candidates": [asdict(item) for item in evidence_candidates],
        "evidence_selections": [asdict(item) for item in evidence_selections],
        "evidence_fingerprint": evidence_fingerprint,
        "reviewed_manifest": reviewed_manifest,
        "metrics": dict(sorted(metrics.items())),
        "limitations": sorted(limitations),
        "creates_truth": False,
        "shadow_only": True,
    }


def evaluate_evidence_benchmark(
    manifest: ReviewedEvidenceManifest,
    *,
    media: Mapping[str, object] | None = None,
    replay_candidates: tuple[EvidenceCandidate, ...] = (),
    replay_proposals: tuple[VisitProposal, ...] = (),
    bounds: EvidenceScoringBounds | None = None,
    provider_identity: dict[str, object] | None = None,
    replay_report_fingerprint: str | None = None,
) -> EvidenceBenchmarkReport:
    """Evaluate reviewed evidence candidates by calling the existing Stage 6
    `score_proposal_evidence` scorer once per reconstructed episode -- this
    function never ranks or selects a candidate itself.

    `replay_candidates`/`replay_proposals` optionally add real
    system-produced episodes (from an already-produced replay report)
    alongside the reviewed-manifest-derived ones. Truth joins a
    replay-sourced candidate through its explicit
    `EvidenceCandidate.source_capture_frame_id` provenance (Stage 6.14) --
    never through its own replay-local `media_asset_id`/`frame_id`,
    filename/path, frame ordering, timestamp equality, or geometry -- see
    `_source_lineage_join` and docs/reviewed-replay-lineage-contract.md.
    When no source lineage is available at all (a pre-Stage-6.14 replay
    report, or a genuinely generic non-temporal-review replay input), the
    affected metrics honestly report `not_evaluated`/`insufficient_truth`
    rather than a fabricated value, and a stable-coded limitation is
    recorded. `media` is transparently extended (`_media_with_source_
    lineage_fallback`) so a replay-sourced candidate can decode the same
    bytes a reviewer looked at, once its lineage is verified safe --
    without this, a replay-sourced candidate has no image bytes available
    under its own replay-local `media_asset_id` and would always score
    `candidate_unavailable` regardless of how correct its lineage is.
    """

    policy_identity = {
        "evidence_scoring_version": EVIDENCE_SCORING_VERSION,
        "bounds": asdict(bounds or EvidenceScoringBounds()),
    }
    reviewed_manifest_dict = manifest.to_semantic_dict()

    if not manifest.candidates and not replay_candidates:
        metrics = {name: _metric(None, STATE_UNSUPPORTED) for name in _ALL_METRIC_NAMES}
        semantic = _semantic_payload(
            EVIDENCE_BENCHMARK_REPORT_SCHEMA_VERSION, manifest.fingerprint, policy_identity, provider_identity,
            replay_report_fingerprint, (), (), (), semantic_fingerprint([]), reviewed_manifest_dict, metrics,
            ("empty_input: no reviewed candidates and no replay-sourced candidates were supplied",),
        )
        return EvidenceBenchmarkReport(
            EVIDENCE_BENCHMARK_REPORT_SCHEMA_VERSION, manifest.fingerprint, policy_identity, provider_identity,
            replay_report_fingerprint, (), (), (), semantic_fingerprint([]), reviewed_manifest_dict, metrics,
            semantic["limitations"], semantic_fingerprint(semantic),
        )

    join_map, lineage_limitations = _source_lineage_join(manifest, replay_candidates)
    scoring_media = _media_with_source_lineage_fallback(media, replay_candidates, join_map)
    manifest_episodes = _build_manifest_episodes(manifest, scoring_media, bounds, join_map)
    replay_episodes = _build_replay_episodes(replay_candidates, replay_proposals, scoring_media, bounds, join_map)
    episodes = tuple(sorted(manifest_episodes + replay_episodes, key=lambda item: item.episode_id))

    ordered_manifest_candidates = sorted(manifest.candidates, key=lambda item: item.candidate_id)
    evidence_candidates = tuple(
        candidate
        for episode in manifest_episodes
        for candidate in (
            _to_evidence_candidate(item)
            for item in ordered_manifest_candidates
            if item.candidate_id in episode.manifest_candidate_ids and item.episode_key == episode.episode_id
        )
    ) + replay_candidates
    evidence_selections = tuple(episode.selection for episode in episodes)
    evidence_fingerprint = semantic_fingerprint([item.semantic_fingerprint for item in evidence_selections])

    metrics = _compute_metrics(episodes, manifest)

    limitations: list[str] = list(lineage_limitations)
    for episode in episodes:
        limitations.extend(episode.selection.limitations)
    # Surface any per-candidate reconstruction caveats (e.g. the ones
    # build_reviewed_evidence_manifest_from_temporal_review attaches) at
    # report level too -- not just buried in reviewed_manifest, where a
    # reader summarizing only top-level limitations would otherwise miss
    # them entirely.
    for item in manifest.candidates:
        limitations.extend(item.limitations)

    semantic = _semantic_payload(
        EVIDENCE_BENCHMARK_REPORT_SCHEMA_VERSION, manifest.fingerprint, policy_identity, provider_identity,
        replay_report_fingerprint, episodes, evidence_candidates, evidence_selections, evidence_fingerprint,
        reviewed_manifest_dict, metrics, tuple(sorted(set(limitations))),
    )
    return EvidenceBenchmarkReport(
        EVIDENCE_BENCHMARK_REPORT_SCHEMA_VERSION, manifest.fingerprint, policy_identity, provider_identity,
        replay_report_fingerprint, episodes, evidence_candidates, evidence_selections, evidence_fingerprint,
        reviewed_manifest_dict, metrics, semantic["limitations"], semantic_fingerprint(semantic),
    )


# --------------------------------------------------------------------------
# Stage 6.6 reviewed-packet derivation (still pure -- session/annotations are
# already-loaded in-memory objects; no filesystem access happens here).
# --------------------------------------------------------------------------

_ROLE_RECONSTRUCTION_LIMITATIONS: tuple[str, ...] = (
    "role_reconstructed_from_temporal_review: role is derived from trigger_reasons/high_resolution "
    "rather than the live tracker's own tracked_best/final_supported distinction, since a static "
    "reviewed packet cannot replay that tracker decision",
    "track_generation_representative: a frame active in more than one simultaneous track generation "
    "is attributed to its lexicographically first generation id, the same documented convention "
    "burst_scheduler_replay.reconstruct_opportunities already uses",
    "dimensions_from_image_decode: width/height are left unset here and resolved from the "
    "referenced frames/<frame_id>.jpg image at scoring time rather than a declared manifest fact",
    "temporal_alignment_not_independently_recorded: Stage 6.6 does not independently record whether a "
    "retained frame was temporally aligned with its track at capture time, so temporal_alignment is left "
    "undeclared for every candidate this derivation produces; the scorer's own temporal-alignment metrics "
    "on a derived manifest reflect this reconstruction gap, not a genuine measurement that the underlying "
    "system produces temporally unaligned evidence",
)


def _int_or_none(value: object) -> int | None:
    return int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None


def _role_from_frame_record(record: Mapping[str, object], *, high_resolution: bool) -> str:
    if high_resolution:
        return "high_resolution_burst"
    triggers = record.get("trigger_reasons") or ()
    if TRIGGER_PRETRIGGER_CONTEXT in triggers:
        return "pretrigger"
    if TRIGGER_POST_TRIGGER_CONTEXT in triggers:
        return "context"
    if record.get("track_generation_ids"):
        return "detector_confirmed"
    return "alternative"


def build_reviewed_evidence_manifest_from_temporal_review(
    session: Mapping[str, object],
    annotations: AnnotationSet,
    *,
    source_description: str,
) -> ReviewedEvidenceManifest:
    """Mechanically derive a reviewed evidence manifest from an
    already-loaded Stage 6.6/6.8 capture-session-manifest dict and its
    reviewed `AnnotationSet` -- a caller never hand-copies data that already
    exists in the reviewed packet. Neither argument is mutated. Only
    reviewed (`is_reviewed`) frames become candidates; an `unreviewed` frame
    contributes nothing (never silently counted as truth). See
    docs/evidence-benchmark-contract.md for the field-by-field mapping and
    its honestly-disclosed reconstruction limitations."""

    frames_by_id: dict[str, Mapping[str, object]] = {
        item["frame_id"]: item
        for item in session.get("frames", ())  # type: ignore[union-attr]
        if isinstance(item, Mapping) and isinstance(item.get("frame_id"), str)
    }
    session_id = str(session.get("session_id") or "")

    candidates: list[ReviewedEvidenceCandidate] = []
    for frame in annotations.frames:
        if not frame.is_reviewed:
            continue
        record = frames_by_id.get(frame.frame_id)
        if record is None:
            continue
        generation_ids = record.get("track_generation_ids") or ()
        track_generation_id = min((str(item) for item in generation_ids), default=None)
        high_resolution = bool(record.get("high_resolution"))
        box = frame.boxes[0] if frame.boxes else None
        usefulness = frame.evidence_usefulness
        provenance = frame.provenance
        visible = (
            "ambiguous" if frame.whole_frame_truth == "ambiguous"
            else "yes" if frame.whole_frame_truth == "yes"
            else "no" if frame.whole_frame_truth == "no" else None
        )
        candidates.append(ReviewedEvidenceCandidate(
            candidate_id=frame.frame_id,
            session_id=session_id,
            role=_role_from_frame_record(record, high_resolution=high_resolution),
            track_generation_id=track_generation_id,
            source_offset_ms=_int_or_none(record.get("session_offset_ms")),
            high_resolution=high_resolution,
            timing_uncertainty_ms=_int_or_none(record.get("temporal_uncertainty_ms")),
            subject_geometry=tuple(box.box) if box is not None else None,
            image_path=f"frames/{frame.frame_id}.jpg",
            content_hash=record.get("content_hash") if isinstance(record.get("content_hash"), str) else None,
            reviewed_subject_visible=visible,
            ambiguous=frame.whole_frame_truth == "ambiguous",
            useful_broad_confirmation=usefulness.broad_animal_confirmation_useful if usefulness else None,
            useful_identification=usefulness.identification_potentially_useful if usefulness else None,
            useful_context=usefulness.context_useful if usefulness else None,
            reviewed_blurred=box.blurred if box is not None else None,
            reviewed_clipped=box.edge_clipped if box is not None else None,
            reviewed_occluded=box.occluded if box is not None else None,
            reviewed_subject_contained=(not box.edge_clipped) if box is not None else None,
            reviewer=provenance.reviewer if provenance else None,
            reviewed_at_iso=provenance.reviewed_at_iso if provenance else None,
            truth_source=provenance.truth_source if provenance else None,
            limitations=_ROLE_RECONSTRUCTION_LIMITATIONS,
        ))

    appearances: list[ReviewedAppearance] = []
    for appearance in annotations.appearances:
        start = frames_by_id.get(appearance.start_frame_id)
        end = frames_by_id.get(appearance.end_frame_id)
        start_offset = _int_or_none(start.get("session_offset_ms")) if start is not None else None
        end_offset = _int_or_none(end.get("session_offset_ms")) if end is not None else None
        if start_offset is None:
            continue
        appearances.append(ReviewedAppearance(
            appearance.appearance_id, session_id, start_offset, max(start_offset, end_offset or start_offset),
        ))

    return ReviewedEvidenceManifest(
        REVIEWED_EVIDENCE_MANIFEST_VERSION, f"temporal-review:{session_id}", source_description,
        tuple(candidates), tuple(appearances),
    )


# --------------------------------------------------------------------------
# Comparison -- deterministic, per-metric classification, no winner score.
# --------------------------------------------------------------------------

_LOWER_IS_BETTER: frozenset[str] = frozenset({
    "identification_clipped_rate", "identification_blurred_unusable_rate", "no_useful_evidence_count",
    "rejected_candidates_count", "evidence_latency_from_appearance_ms", "burst_request_to_capture_latency_ms",
    "temporal_uncertainty_ms_average", "stale_generation_rejection_count",
    "episodes_with_no_useful_automatic_identification", "episodes_requiring_alternate_inspection",
    "selected_evidence_temporal_uncertain_rate",
})


def compare_evidence_benchmark_reports(baseline: dict[str, object], candidate: dict[str, object]) -> dict[str, object]:
    """Classify every metric present in either report independently, exactly
    mirroring `replay.compare_replay_reports`'s own established shape
    (renamed left/right to baseline/candidate): `baseline better`,
    `candidate better`, `equivalent`, `insufficient truth`, or
    `unsupported for one side`. Never produces an aggregate winner score."""

    baseline_metrics = baseline.get("metrics") if isinstance(baseline.get("metrics"), dict) else {}
    candidate_metrics = candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {}
    names = sorted(set(baseline_metrics) | set(candidate_metrics))
    comparisons: list[dict[str, object]] = []
    for name in names:
        baseline_metric = baseline_metrics.get(name)
        candidate_metric = candidate_metrics.get(name)
        baseline_state = baseline_metric.get("state") if isinstance(baseline_metric, dict) else STATE_NOT_EVALUATED
        candidate_state = candidate_metric.get("state") if isinstance(candidate_metric, dict) else STATE_NOT_EVALUATED
        baseline_value = baseline_metric.get("value") if isinstance(baseline_metric, dict) else None
        candidate_value = candidate_metric.get("value") if isinstance(candidate_metric, dict) else None
        difference = (
            candidate_value - baseline_value
            if baseline_state == candidate_state == STATE_EVALUATED
            and isinstance(baseline_value, (int, float)) and isinstance(candidate_value, (int, float))
            else None
        )
        if baseline_state == STATE_INSUFFICIENT_TRUTH or candidate_state == STATE_INSUFFICIENT_TRUTH:
            classification = "insufficient truth"
        elif baseline_state != STATE_EVALUATED or candidate_state != STATE_EVALUATED:
            classification = "unsupported for one side"
        elif baseline_value == candidate_value:
            classification = "equivalent"
        elif isinstance(baseline_value, (int, float)) and isinstance(candidate_value, (int, float)):
            lower_is_better = name in _LOWER_IS_BETTER
            candidate_better = candidate_value < baseline_value if lower_is_better else candidate_value > baseline_value
            classification = "candidate better" if candidate_better else "baseline better"
        else:
            classification = "unsupported for one side"
        comparisons.append({
            "metric": name,
            "baseline": {"state": baseline_state, "value": baseline_value},
            "candidate": {"state": candidate_state, "value": candidate_value},
            "difference": difference,
            "classification": classification,
        })
    semantic = {"comparison_version": "evidence-benchmark-comparison-v1", "metrics": comparisons}
    return {**semantic, "semantic_fingerprint": semantic_fingerprint(semantic)}


__all__ = [
    "EVIDENCE_BENCHMARK_REPORT_SCHEMA_VERSION",
    "EVIDENCE_BENCHMARK_VERSION",
    "METRIC_STATES",
    "REVIEWED_EVIDENCE_MANIFEST_VERSION",
    "STATE_EVALUATED",
    "STATE_INSUFFICIENT_TRUTH",
    "STATE_NOT_EVALUATED",
    "STATE_UNSUPPORTED",
    "EpisodeResult",
    "EvidenceBenchmarkError",
    "EvidenceBenchmarkReport",
    "ReviewedAppearance",
    "ReviewedEvidenceCandidate",
    "ReviewedEvidenceManifest",
    "build_reviewed_evidence_manifest_from_temporal_review",
    "compare_evidence_benchmark_reports",
    "evaluate_evidence_benchmark",
]
