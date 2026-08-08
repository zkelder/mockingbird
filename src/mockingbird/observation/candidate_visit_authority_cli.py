"""Stage 7 bounded, explicit candidate-Visit authority trial.

`python -m mockingbird candidate-authority-trial` runs the real, paired
Camera Node live-shadow pipeline (Stage 5's `CameraNodeAnalysisSource` /
`CameraNodeHttpTransport` / `LiveCameraNodeShadowSession`, reused completely
unchanged -- exactly the same connection-building convention every prior
live Camera Node CLI in this package, `temporal_capture_cli.py`, already
uses) for a hard-bounded duration, periodically running the unmodified
Stage 6.19 assembler over the live session's own accumulated `TrackUpdate`s,
and -- only with `--activate` -- attempting a real Stage 7 candidate Visit
for each newly assembled proposal through the real product repository.

Without `--activate` this is a safe, hardware-connectivity/mechanics-only
dry run: authority state is read but never changed, so it behaves exactly
like ordinary shadow observation (see "Existing Snapshot/current production
behavior must remain available and unchanged unless the explicit authority
mode is enabled" in docs/candidate-visit-authority-contract.md).

Hard trial bounds (see "Real controlled trial" in the contract doc):
`--duration-seconds` is capped at 600 (10 minutes); `--max-candidates` is
capped at 3. Evidence is sourced only from the live session's own bounded
high-resolution burst cache (`LiveCameraNodeShadowSession.
temporary_burst_payload`) -- the "already-captured real evidence burst"
this stage's evidence-persistence policy names first; a candidate with no
retrievable burst evidence fails safely rather than persisting with
fabricated or missing evidence.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from mockingbird.observation.camera_node_live import (
    CameraNodeAnalysisSource,
    CameraNodeHttpTransport,
    LiveCameraNodeShadowSession,
)
from mockingbird.observation.candidate_visit_adapter import CandidateVisitAuthorityAdapter
from mockingbird.observation.candidate_visit_authority import ObservationAuthorityMode
from mockingbird.observation.contracts import EvidenceCandidate, TrackUpdate
from mockingbird.observation.frame_driven_provider import FrameDrivenObservationProvider, FrameDrivenProviderConfiguration
from mockingbird.observation.onnx_provider import OnnxCudaObservationProvider, OnnxModelBundle
from mockingbird.observation.temporal_capture_io import load_camera_node_connection_config
from mockingbird.observation.visit_episode_assembler import ASSEMBLER_VERSION, assemble_visit_episodes, build_tracklets
from mockingbird.repository.product_repository import ProductRepository
from mockingbird.source_providers.camera_node import CameraNodeClientError
from mockingbird.storage.database import resolve_database_url, resolve_media_root

MAX_TRIAL_DURATION_SECONDS = 600
MAX_TRIAL_CANDIDATES = 3
_BATCH_FRAMES = 20
_ASSEMBLY_TICK_SECONDS = 10.0


def _trial_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bounded Stage 7 candidate-Visit authority trial.")
    parser.add_argument("--camera-node-config", required=True, type=Path, help="Ignored local JSON: base_address/credential/camera_id/stream_id/evidence_profile_id.")
    parser.add_argument("--provider-config", required=True, type=Path, help="Existing frame-driven provider configuration JSON.")
    parser.add_argument("--stream-id-in-product", required=True, help="The product Stream id this trial's candidates should attach to (must already exist).")
    parser.add_argument("--duration-seconds", type=int, default=180, help=f"Bounded trial duration, hard-capped at {MAX_TRIAL_DURATION_SECONDS}.")
    parser.add_argument("--max-candidates", type=int, default=MAX_TRIAL_CANDIDATES, help=f"Trial-level candidate stop bound, hard-capped at {MAX_TRIAL_CANDIDATES}.")
    parser.add_argument("--activate", action="store_true", help="Explicitly enable candidate_visit authority for this trial. Omit for a safe shadow-only dry run.")
    parser.add_argument("--db-url", default=None, help="Override the product database URL. Defaults to the real app's own resolved database.")
    parser.add_argument("--media-root", type=Path, default=None, help="Override the product media root. Defaults to the real app's own resolved media root.")
    parser.add_argument("--output", type=Path, default=None, help="Optional path to write the final bounded JSON trial summary.")
    parser.add_argument("--review-score-threshold", type=float, default=0.02, help="Low detector threshold, matching temporal-capture's own review-only convention -- never a deployed default.")
    return parser


def _validate_bounds(args: argparse.Namespace) -> None:
    if not 1 <= args.duration_seconds <= MAX_TRIAL_DURATION_SECONDS:
        raise ValueError(f"trial_duration_must_be_between_1_and_{MAX_TRIAL_DURATION_SECONDS}_seconds")
    if not 1 <= args.max_candidates <= MAX_TRIAL_CANDIDATES:
        raise ValueError(f"trial_max_candidates_must_be_between_1_and_{MAX_TRIAL_CANDIDATES}")


def _burst_evidence_bytes(
    session: LiveCameraNodeShadowSession, candidates: tuple[EvidenceCandidate, ...],
) -> dict[str, bytes]:
    bytes_by_media_id: dict[str, bytes] = {}
    for candidate in candidates:
        if candidate.role != "high_resolution_burst":
            continue
        content_hash = dict(candidate.quality_facts).get("content_hash")
        if not isinstance(content_hash, str):
            continue
        payload = session.temporary_burst_payload(content_hash)
        if payload:
            bytes_by_media_id[candidate.media_asset_id] = payload
    return bytes_by_media_id


class _TrialState:
    def __init__(self) -> None:
        self.all_track_updates: list[TrackUpdate] = []
        self.all_evidence_candidates: list[EvidenceCandidate] = []
        self.attempted_proposal_ids: set[str] = set()
        self.candidates_created = 0
        self.attempts: list[dict[str, object]] = []
        self.proposals_observed = 0


def _record_result(payload: object, state: _TrialState) -> None:
    if payload is None:
        return
    results = payload if isinstance(payload, tuple) else (payload,)
    for result in results:
        state.all_track_updates.extend(result.track_updates)
        state.all_evidence_candidates.extend(result.evidence_candidates)


def _run_assembly_tick(
    *, state: _TrialState, stream_id: str, session: LiveCameraNodeShadowSession,
    adapter: CandidateVisitAuthorityAdapter, max_candidates: int, activated: bool,
) -> bool:
    """Returns True if the trial's own candidate stop bound has been
    reached. A no-op (returns False, prints nothing new) when nothing new
    has been assembled since the previous tick."""

    evidence_by_generation: dict[str, list[str]] = {}
    for candidate in state.all_evidence_candidates:
        if candidate.track_generation_id:
            evidence_by_generation.setdefault(candidate.track_generation_id, []).append(candidate.media_asset_id)
    tracklets = build_tracklets(
        tuple(state.all_track_updates), stream_id=stream_id,
        evidence_candidate_ids_by_generation={key: tuple(value) for key, value in evidence_by_generation.items()},
    )
    proposals = assemble_visit_episodes(tracklets).proposals
    new_proposals = [item for item in proposals if item.proposal_id not in state.attempted_proposal_ids]
    if not new_proposals:
        return False

    candidates_by_id = {item.media_asset_id: item for item in state.all_evidence_candidates}
    for proposal in new_proposals:
        state.attempted_proposal_ids.add(proposal.proposal_id)
        state.proposals_observed += 1
        relevant = tuple(
            candidates_by_id[media_id] for media_id in proposal.evidence_candidate_ids if media_id in candidates_by_id
        )
        evidence_bytes = _burst_evidence_bytes(session, relevant)
        outcome = adapter.attempt_candidate(
            proposal, evidence_candidates=relevant, evidence_bytes=evidence_bytes, observed_at=datetime.now(UTC),
        )
        entry = {
            "proposal_id": outcome.proposal_id,
            "outcome": outcome.outcome,
            "reason": outcome.reason,
            "visit_id": outcome.visit_id,
        }
        state.attempts.append(entry)
        print(f"[stage7-trial] proposal={outcome.proposal_id} -> {outcome.outcome} ({outcome.reason})", file=sys.stderr)
        if outcome.created:
            state.candidates_created += 1
            print(f"[stage7-trial] CANDIDATE CREATED visit_id={outcome.visit_id}", file=sys.stderr)
            if activated and state.candidates_created >= max_candidates:
                return True
    return False


async def _run_trial(args: argparse.Namespace) -> dict[str, object]:
    _validate_bounds(args)
    connection = load_camera_node_connection_config(args.camera_node_config)
    configuration = FrameDrivenProviderConfiguration.load(args.provider_config)
    bundle = OnnxModelBundle.load(configuration.model_bundle_path)
    review_bundle = replace(bundle, score_threshold=args.review_score_threshold)
    detector = OnnxCudaObservationProvider(bundle=review_bundle)
    provider = FrameDrivenObservationProvider(detector=detector, settings=configuration.settings)
    provider.load()

    repository = ProductRepository(
        db_url=args.db_url or resolve_database_url(None), media_root=args.media_root or resolve_media_root(None),
    )
    started_activation_status = None
    try:
        if args.activate:
            started_activation_status = repository.set_observation_authority_mode(
                ObservationAuthorityMode.candidate_visit,
                max_candidates_per_session=args.max_candidates,
                max_candidates_per_hour=max(args.max_candidates, MAX_TRIAL_CANDIDATES),
            )
            print(
                f"[stage7-trial] authority ACTIVATED: activation_boundary_at={started_activation_status.activation_boundary_at.isoformat()}",
                file=sys.stderr,
            )
        else:
            print("[stage7-trial] --activate not passed: running shadow-only (no candidate Visit can be created)", file=sys.stderr)

        source = CameraNodeAnalysisSource(connection.stream_id, analysis_excluded_regions=())
        transport = CameraNodeHttpTransport(
            base_address=connection.base_address, credential=connection.credential, camera_id=connection.camera_id,
            stream_id=connection.stream_id, evidence_profile_id=connection.evidence_profile_id,
        )
        session = LiveCameraNodeShadowSession(
            source=source, transport=transport, provider=provider, evidence_profile_id=connection.evidence_profile_id,
        )
        adapter = CandidateVisitAuthorityAdapter(
            repository, detector_provenance=detector.provider_id if hasattr(detector, "provider_id") else "onnx-cuda",
            tracker_provenance=provider.provider_id, provider_key=provider.provider_id,
        )
        state = _TrialState()
        started_wall = datetime.now(UTC)
        stopped_reason = "duration_elapsed"
        try:
            session.start()
            last_tick = started_wall
            while (datetime.now(UTC) - started_wall).total_seconds() < args.duration_seconds:
                try:
                    results = await session.run(maximum_frames=_BATCH_FRAMES)
                except (CameraNodeClientError, ValueError) as error:
                    # Stage 6.11B: an ordinary benign HTTP reconnect never
                    # raises here at all (bridged internally, exactly as
                    # `temporal_capture_cli._CaptureLoop.run` already
                    # documents) -- anything that still reaches this handler
                    # is a genuine unrecoverable transport/source error.
                    # Reported honestly as a clean stop, never silently
                    # retried, and never allowed to crash the trial without
                    # a usable summary.
                    print(f"[stage7-trial] transport error, stopping cleanly: {error}", file=sys.stderr)
                    stopped_reason = "transport_error"
                    break
                if not results:
                    stopped_reason = "stream_ended"
                    break
                _record_result(results, state)
                now = datetime.now(UTC)
                if (now - last_tick).total_seconds() >= _ASSEMBLY_TICK_SECONDS:
                    last_tick = now
                    if _run_assembly_tick(
                        state=state, stream_id=args.stream_id_in_product, session=session, adapter=adapter,
                        max_candidates=args.max_candidates, activated=args.activate,
                    ):
                        stopped_reason = "max_candidates_reached"
                        break
        finally:
            final_results = session.stop()
            _record_result(final_results, state)
            _run_assembly_tick(
                state=state, stream_id=args.stream_id_in_product, session=session, adapter=adapter,
                max_candidates=args.max_candidates, activated=args.activate,
            )
            provider.close()

        ended_wall = datetime.now(UTC)
        final_status = repository.get_observation_authority_state()
        summary = {
            "trial_version": "candidate-visit-authority-trial-v1",
            "assembler_version": ASSEMBLER_VERSION,
            "activated": args.activate,
            "started_at": started_wall.isoformat(),
            "ended_at": ended_wall.isoformat(),
            "duration_seconds": round((ended_wall - started_wall).total_seconds(), 3),
            "stopped_reason": stopped_reason,
            "track_updates_observed": len(state.all_track_updates),
            "evidence_candidates_observed": len(state.all_evidence_candidates),
            "proposals_observed": state.proposals_observed,
            "candidates_created": state.candidates_created,
            "attempts": state.attempts,
            "authority_status": {
                "mode": final_status.mode,
                "activation_boundary_at": (
                    final_status.activation_boundary_at.isoformat() if final_status.activation_boundary_at else None
                ),
                "candidates_created_in_session": final_status.candidates_created_in_session,
                "candidates_created_in_trailing_hour": final_status.candidates_created_in_trailing_hour,
                "proposals_observed_count": final_status.proposals_observed_count,
                "failure_count": final_status.failure_count,
                "last_failure_code": final_status.last_failure_code,
            },
        }
        return summary
    finally:
        repository.close()


def run_trial(argv: list[str] | None = None) -> int:
    args = _trial_parser().parse_args(argv)
    try:
        summary = asyncio.run(_run_trial(args))
    except (ValueError, CameraNodeClientError) as error:
        print(f"Stage 7 candidate authority trial rejected: {error}", file=sys.stderr)
        return 2
    print(json.dumps(summary, indent=2))
    if args.output is not None:
        args.output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return 0


def main_trial() -> None:
    raise SystemExit(run_trial())
