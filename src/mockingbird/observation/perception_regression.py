"""Perception Replay Regression Harness v1: orchestration.

Composes existing, unmodified production/replay computation into one
coherent "full funnel" regression run -- detection/tracking (`replay.
ReplayRunner`, reusing whichever real Observation Engine provider is
selected), Visit episode assembly (`replay.assemble_visit_episode_report`,
Stage 6.19), and shadow admission (`admission_replay.evaluate_shadow_
admission`, new in this milestone, itself reusing the real, unmodified
Stage 7 gates). Nothing in this module reimplements perception; it only
sequences and reports on already-real computation, plus adds the run-level
provenance (code HEAD, harness version, seed, timestamp) none of the
underlying pieces carry on their own.

Logical-time mode is the only mode this harness implements: every temporal
fact throughout the funnel is driven by each frame's own recorded
`source_offset_ms` (and, for acceptance-recorder-derived input, real
`captured_at_iso`), never a real sleep. See "Logical-time mode" in
docs/perception-replay-regression-harness-contract.md for the explicit
contrast with the optional, unbuilt real-time mode.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import subprocess

from mockingbird.observation.admission_replay import (
    AdmissionReplayReport,
    IsolatedAdmissionRepository,
    admission_report_to_json,
    evaluate_shadow_admission,
)
from mockingbird.observation.contracts import ObservationProvider
from mockingbird.observation.replay import (
    BenchmarkManifest,
    ExpectedAppearance,
    ExpectedDetection,
    ExpectedVisit,
    ReplayFrame,
    ReplayInput,
    ReplayReport,
    ReplayRunner,
    ReplayValidationError,
    VisitEpisodeAssemblyReport,
    assemble_visit_episode_report,
    semantic_fingerprint,
)
from mockingbird.observation.replay_io import ReplayBundle
from mockingbird.observation.visit_episode_assembler import VisitAssemblyConfiguration
from mockingbird.web_app import find_workspace_root

HARNESS_VERSION = "perception-replay-regression-harness-v1"


def _git_head(*, cwd: Path | None = None) -> str | None:
    """Best-effort, never-fatal: a regression run's own reproducibility is a
    disclosed fact, not a hard requirement -- an environment with no git
    binary or a detached/shallow checkout still produces a usable report,
    honestly recording `None` rather than failing the whole run."""

    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=cwd or find_workspace_root(), capture_output=True,
            text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    head = result.stdout.strip()
    return head or None


@dataclass(frozen=True)
class RegressionRunProvenance:
    """Enough to reproduce or explain one run after the fact -- see "Replay
    run manifest" in docs/perception-replay-regression-harness-contract.md.
    Never includes an absolute path, host name, or PID (those stay in each
    stage's own separate non-semantic `execution` section, exactly like
    `replay_io.write_replay_report` already keeps them out of its own
    semantic payload)."""

    harness_version: str
    code_head: str | None
    run_started_at: str
    seed: int | None
    provider_key: str
    stream_id: str | None
    admission_evaluated: bool


@dataclass(frozen=True)
class PerceptionFunnelReport:
    """The combined result of one regression run: raw replay (Stage 2),
    assembled Visit episodes (Stage 6.19), and shadow admission (new) --
    each stage's own metrics remain independently visible, exactly like
    `VisitEpisodeAssemblyReport` already keeps tracker-level fragmentation
    visible independent of what assembly does about it. `admission` is
    `None` only when the caller explicitly opted out (`run_admission=
    False`) or supplied no `stream_id` -- never silently skipped."""

    replay: ReplayReport
    assembly: VisitEpisodeAssemblyReport
    admission: AdmissionReplayReport | None
    provenance: RegressionRunProvenance
    semantic_fingerprint: str


def _provider_capabilities_summary(provider: ObservationProvider) -> dict[str, Any]:
    capabilities = provider.capabilities
    return {name: getattr(capabilities, name) for name in sorted(vars(capabilities))}


async def run_perception_regression(
    bundle: ReplayBundle,
    *,
    provider: ObservationProvider,
    provider_key: str,
    assembly_config: VisitAssemblyConfiguration | None = None,
    run_admission: bool = True,
    base_observed_at: datetime | None = None,
    seed: int | None = None,
    known_horizon_ms: int | None = None,
) -> PerceptionFunnelReport:
    """Run the complete additive funnel over one already-loaded
    `ReplayBundle` against one already-constructed provider.

    Admission's Stream identity is always `bundle.replay.stream_id` --
    deliberately not a second, separately-supplied parameter: every proposal
    the assembler/provider produce already carries `stream_id` from the
    replay input itself (`FramePacket.stream_id` -> `TrackUpdate` ->
    `AssembledVisitProposal.stream_id`), and the real Stage 7 gates check
    *that* field's own authority state, not any value a caller passes
    alongside it. Passing a different identity here would silently activate
    authority for a Stream no proposal actually claims, and the real
    admission call would then honestly (but confusingly) block everything
    as `blocked_shadow_mode`. One identity flows through the whole funnel;
    `bundle.replay.stream_id` must therefore already be replay-namespaced
    (see `admission_replay.require_replay_stream_id`) whenever `run_
    admission` is left at its default `True`.

    `run_admission` defaults `True`; a caller measuring only detection/
    tracking/assembly (for example a fast provider-comparison pass) may set
    it `False` explicitly rather than this function silently deciding for
    them. Admission uses a fresh, disposable, isolated repository for the
    duration of this call only -- see `IsolatedAdmissionRepository`.
    """

    started_at = datetime.now(UTC).isoformat()
    replay_report = await ReplayRunner({provider_key: provider}).run(
        bundle.replay, bundle.manifest, provider_key=provider_key, thresholds=bundle.thresholds,
    )
    assembly = assemble_visit_episode_report(replay_report, bundle.manifest, assembly_config)

    stream_id = bundle.replay.stream_id if run_admission else None
    admission: AdmissionReplayReport | None = None
    if run_admission:
        anchor = base_observed_at or datetime(2026, 1, 1, tzinfo=UTC)
        evidence_bytes = _evidence_bytes_from_frames(bundle, replay_report)
        with IsolatedAdmissionRepository(stream_id=stream_id, activation_boundary_at=anchor) as repository:
            admission = evaluate_shadow_admission(
                assembly.proposals, repository=repository, stream_id=stream_id,
                evidence_candidates=replay_report.evidence_candidates,
                evidence_bytes=evidence_bytes, base_observed_at=anchor,
            )

    provenance = RegressionRunProvenance(
        harness_version=HARNESS_VERSION, code_head=_git_head(), run_started_at=started_at, seed=seed,
        provider_key=provider_key, stream_id=stream_id, admission_evaluated=admission is not None,
    )
    semantic = {
        "harness_version": HARNESS_VERSION,
        "replay_semantic_fingerprint": replay_report.semantic_fingerprint,
        "assembly_semantic_fingerprint": assembly.semantic_fingerprint,
        "admission": admission_report_to_json(admission) if admission is not None else None,
        "seed": seed,
    }
    return PerceptionFunnelReport(
        replay=replay_report, assembly=assembly, admission=admission, provenance=provenance,
        semantic_fingerprint=semantic_fingerprint(semantic),
    )


def _evidence_bytes_from_frames(bundle: ReplayBundle, report: ReplayReport) -> dict[str, bytes]:
    """Real evidence bytes, read from the same source frame files the
    replay input itself already validated -- never fabricated, and skipped
    (not substituted) for any `media_asset_id` with no resolvable source
    file, exactly like `candidate_visit_adapter._build_evidence_items`'s own
    discipline one layer downstream."""

    path_by_media_asset_id = {
        frame.media_asset_id: source.source_path
        for frame, source in zip(report.frames, bundle.replay.frames)
        if source.source_path is not None
    }
    evidence_bytes: dict[str, bytes] = {}
    for candidate in report.evidence_candidates:
        source_path = path_by_media_asset_id.get(candidate.media_asset_id)
        if source_path is None:
            continue
        try:
            evidence_bytes[candidate.media_asset_id] = Path(source_path).read_bytes()
        except OSError:
            continue
    return evidence_bytes


def perception_regression_report_to_json(report: PerceptionFunnelReport) -> dict[str, Any]:
    """Deterministic, JSON-safe projection of the combined report, following
    `replay_io.write_replay_report`'s own `semantic`/`execution` split: this
    function returns only the semantic half (safe to hash/compare/commit to
    a fixture's expected-output record); a caller's own I/O layer adds a
    separate, non-semantic `execution` section (wall time, host, absolute
    paths) the way `perception_regression_cli.py` does."""

    return {
        "schema_version": 1,
        "harness_version": report.provenance.harness_version,
        "replay": {
            "semantic_fingerprint": report.replay.semantic_fingerprint,
            "metrics": report.replay.metrics,
            "threshold_results": list(report.replay.threshold_results),
            "proposal_count": len(report.replay.proposals),
            "detection_count": len(report.replay.detections),
            "track_update_count": len(report.replay.track_updates),
            "evidence_candidate_count": len(report.replay.evidence_candidates),
        },
        "assembly": {
            "semantic_fingerprint": report.assembly.semantic_fingerprint,
            "assembly_metrics": report.assembly.assembly_metrics,
            "visit_truth_metrics": report.assembly.visit_truth_metrics,
            "assembled_proposal_count": len(report.assembly.proposals),
        },
        "admission": admission_report_to_json(report.admission) if report.admission is not None else None,
        "provenance": {**asdict(report.provenance)},
        "semantic_fingerprint": report.semantic_fingerprint,
    }


# =============================================================================
# Bounded time-window selection over an already-loaded, truth-bearing
# `ReplayBundle` -- distinct from `perception_regression_io.load_acceptance_
# recording`'s own windowing (which has no truth to preserve at all). Purely
# additive: never mutates the supplied bundle.
# =============================================================================


def select_time_window(bundle: ReplayBundle, *, start_offset_ms: int, end_offset_ms: int) -> ReplayBundle:
    """Return a new `ReplayBundle` containing only frames within
    `[start_offset_ms, end_offset_ms]` (inclusive), re-indexed to start at
    offset 0 (required by `ReplayInput`'s own strictly-increasing-from-a-
    stable-origin contract). Truth objects (`appearances`, `visits`,
    `detections`) are kept only when *fully* contained in the window --
    never truncated to a partial appearance/Visit, which would fabricate a
    boundary no reviewer ever actually drew. `evidence` truth is untouched
    (it is not frame-position-indexed the way `detections` is) -- a caller
    windowing a manifest with evidence truth should treat any surviving
    evidence-candidate reference as informational only, since its own
    generation may fall outside the selected window.
    """

    if start_offset_ms > end_offset_ms:
        raise ReplayValidationError("invalid_time_window")
    kept_frames = [frame for frame in bundle.replay.frames if start_offset_ms <= frame.source_offset_ms <= end_offset_ms]
    if not kept_frames:
        raise ReplayValidationError("empty_window_selection")
    origin_ms = kept_frames[0].source_offset_ms
    old_to_new_index = {frame.index: index for index, frame in enumerate(kept_frames)}
    rebased_frames = tuple(
        ReplayFrame(
            index, frame.source_offset_ms - origin_ms, frame.content_hash, frame.source_path,
            frame.analysis_excluded_regions, captured_at_iso=frame.captured_at_iso,
            source_sequence=frame.source_sequence, original_source_offset_ms=frame.original_source_offset_ms,
            connection_segment_id=frame.connection_segment_id,
            connection_segment_ordinal=frame.connection_segment_ordinal,
            provider_generation=frame.provider_generation, temporal_discontinuity=frame.temporal_discontinuity,
            temporal_uncertainty_ms=frame.temporal_uncertainty_ms,
            source_capture_frame_id=frame.source_capture_frame_id,
            source_capture_session_id=frame.source_capture_session_id, session_sequence=frame.session_sequence,
        )
        for index, frame in enumerate(kept_frames)
    )
    replay = ReplayInput(
        bundle.replay.input_id, bundle.replay.stream_id, bundle.replay.width, bundle.replay.height,
        bundle.replay.nominal_fps, rebased_frames,
    )

    kept_appearances = tuple(
        ExpectedAppearance(
            item.appearance_id, item.start_offset_ms - origin_ms, item.end_offset_ms - origin_ms,
            item.outcome, item.ambiguous,
        )
        for item in bundle.manifest.appearances
        if start_offset_ms <= item.start_offset_ms and item.end_offset_ms <= end_offset_ms
    )
    kept_appearance_ids = {item.appearance_id for item in kept_appearances}
    kept_visits = tuple(
        ExpectedVisit(
            item.visit_id, item.appearance_ids, item.start_offset_ms - origin_ms, item.end_offset_ms - origin_ms,
            item.outcome, item.zone_id, item.ambiguous, item.broad_class, item.entry_uncertain,
            item.exit_uncertain, item.source_capture_frame_ids, item.reviewer,
        )
        for item in bundle.manifest.visits
        if (
            start_offset_ms <= item.start_offset_ms and item.end_offset_ms <= end_offset_ms
            and set(item.appearance_ids) <= kept_appearance_ids
        )
    )
    kept_detections = tuple(
        ExpectedDetection(item.annotation_id, old_to_new_index[item.frame_index], item.broad_class, item.bounding_box)
        for item in bundle.manifest.detections
        if item.frame_index in old_to_new_index
    )
    manifest = BenchmarkManifest(
        bundle.manifest.version, f"{bundle.manifest.benchmark_id}:window[{start_offset_ms}-{end_offset_ms}]",
        replay.fingerprint, kept_appearances, kept_visits, kept_detections, bundle.manifest.evidence,
    )
    return ReplayBundle(replay, manifest, bundle.thresholds)


# =============================================================================
# Differential capability: baseline vs. candidate for the same replay input.
# =============================================================================

_ADMISSION_COMPARISON_KEYS = ("created", "blocked_ambiguous_boundary", "blocked_continuation_pending",
    "blocked_missing_evidence", "blocked_scene_confusor_suspected", "reject_no_identification_or_context",
    "reject_subject_geometry_invalid", "reject_insufficient_proposal_support", "failed")

_ASSEMBLY_COMPARISON_KEYS = ("tracklets_input", "episode_merges", "separate_decisions", "ambiguous_decisions",
    "incompatible_decisions", "assembled_visit_proposals")


def compare_perception_regression_reports(baseline: PerceptionFunnelReport, candidate: PerceptionFunnelReport) -> dict[str, Any]:
    """Baseline-vs-candidate differential for the same replay input: reuses
    `replay.compare_replay_reports` for every detection/tracking/proposal
    metric unchanged, and adds the same honest evaluated/not-evaluated
    comparison discipline for the two stages that module does not cover --
    assembly and admission. Never invents a value neither side actually
    produced.
    """

    from mockingbird.observation.replay import compare_replay_reports

    base = compare_replay_reports(baseline.replay, candidate.replay)

    assembly_comparisons = []
    for key in _ASSEMBLY_COMPARISON_KEYS:
        left = baseline.assembly.assembly_metrics.get(key, {})
        right = candidate.assembly.assembly_metrics.get(key, {})
        left_value = left.get("value") if isinstance(left, dict) else None
        right_value = right.get("value") if isinstance(right, dict) else None
        assembly_comparisons.append({
            "metric": key, "left": left_value, "right": right_value,
            "classification": "equivalent" if left_value == right_value else "changed",
        })

    admission_comparisons = []
    left_counts = baseline.admission.outcome_counts if baseline.admission is not None else None
    right_counts = candidate.admission.outcome_counts if candidate.admission is not None else None
    for key in _ADMISSION_COMPARISON_KEYS:
        if left_counts is None or right_counts is None:
            admission_comparisons.append({"metric": key, "left": None, "right": None, "classification": "not_evaluated"})
            continue
        left_value = left_counts.get(key, 0)
        right_value = right_counts.get(key, 0)
        admission_comparisons.append({
            "metric": key, "left": left_value, "right": right_value,
            "classification": "equivalent" if left_value == right_value else "changed",
        })

    semantic = {
        "comparison_version": "perception-regression-comparison-v1",
        "replay_comparison": base,
        "assembly_comparisons": assembly_comparisons,
        "admission_comparisons": admission_comparisons,
    }
    return {**semantic, "semantic_fingerprint": semantic_fingerprint(semantic)}
