"""Command entry points for the Stage 6.6 bounded reviewed temporal capture
against a paired Camera Node.

python -m mockingbird temporal-capture \\
  --camera-node-config <ignored-config.json> \\
  --provider frame-driven-onnx-cuda --provider-config <ignored-model-config.json> \\
  --output <ignored-output-directory> --duration <bounded-seconds> \\
  --scene-id <stable-physical-scene-id> \\
  --capture-purpose training_candidate|holdout_v2_candidate

python -m mockingbird temporal-capture-mark \\
  --capture <capture-directory> --kind wildlife_visible_now [--note "..."]

`temporal-capture` opens exactly one authenticated Camera Node connection,
retains only bounded-trigger frames, and writes an ignored, local capture
directory (frames + `capture-session-manifest.json`). It creates no product
record. See docs/temporal-review-capture-contract.md.

`--scene-id` is required and names the stable physical scene/camera-view
this session belongs to (see docs/wildlife-detector-training-contract.md
"Scene identity and multi-scene acquisition"); `--capture-purpose` (default
`training_candidate`) declares whether this session's frames are ever
eligible for training or reserved as Holdout v2 -- see
`mockingbird.training.wildlife_multiscene`. A running capture stops early
and finalizes its manifest cleanly (`stop_condition=manual_stop`) on one
Ctrl-C (SIGINT) or SIGTERM, in addition to its normal `--duration`/resource
bounds.
"""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
import signal
import sys
from uuid import uuid4

from mockingbird.observation.camera_node_live import (
    CameraNodeAnalysisSource,
    CameraNodeHttpTransport,
    LiveCameraNodeShadowSession,
)
from mockingbird.observation.contracts import EvidenceCandidate
from mockingbird.observation.frame_driven_provider import (
    FrameDrivenObservationProvider,
    FrameDrivenProviderConfiguration,
)
from mockingbird.observation.motion_proposal_strategy import (
    FULL_FRAME_PLUS_MOTION_PROPOSALS,
    FrameIdentity,
    generate_proposals,
)
from mockingbird.observation.onnx_provider import OnnxCudaObservationProvider, OnnxModelBundle
from mockingbird.source_providers.camera_node import CameraNodeClientError
from mockingbird.observation.temporal_capture import (
    CAPTURE_MANIFEST_SCHEMA_VERSION,
    CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE,
    CAPTURE_PURPOSE_TRAINING_CANDIDATE,
    CAPTURE_PURPOSES,
    SCENE_ID_PATTERN,
    STOP_ACTIVE_TRACK_LIMIT,
    STOP_BYTE_LIMIT,
    STOP_DURATION_ELAPSED,
    STOP_FRAME_LIMIT,
    STOP_HIGH_RESOLUTION_LIMIT,
    STOP_MANUAL,
    STOP_MARKER_LIMIT,
    STOP_STREAM_ENDED,
    STOP_TRANSPORT_ERROR,
    TRIGGER_GENERATION_OR_SEQUENCE_DISCONTINUITY,
    TRIGGER_HIGH_RESOLUTION_BURST,
    TRIGGER_MOTION_PROPOSAL_GENERATED,
    TRIGGER_OPERATOR_MARKER,
    TRIGGER_POST_TRIGGER_CONTEXT,
    TRIGGER_PRETRIGGER_CONTEXT,
    TRIGGER_PRIVACY_IGNORE_INTERACTION,
    TRIGGER_RECURRING_STATIC_GEOMETRY,
    CaptureBounds,
    CaptureSessionConfig,
    CaptureSessionManifest,
    OperatorMarker,
    PeriodicNegativeScheduler,
    RecurringGeometryTracker,
    RetainedFrameRecord,
    TemporalCaptureError,
    attach_session_timeline,
    classify_detection_triggers,
    correlate_markers_to_frames,
    has_track_event,
    markers_near,
)
from mockingbird.observation.temporal_capture_io import (
    load_camera_node_connection_config,
    read_operator_markers,
    safe_capture_output_directory,
    write_capture_manifest,
    write_frame_bytes,
    write_operator_marker,
)

BATCH_FRAMES = 12
# Each batch opens its own bounded transport connection (see
# CameraNodeHttpTransport.iter_analysis_frames). Confirmed against the real
# Camera Node: every fresh connection restarts its own sequence header, but
# (Stage 6.11B) an ordinary reconnect like this is now recognized as a
# benign transport-segment transition -- CameraNodeAnalysisSource/
# FrameDrivenObservationProvider bridge it transparently, so a batch
# boundary no longer forces pretrigger/motion-proposal continuity to break
# by itself (only a genuine source-generation reset still does that; see
# `_process_result`'s `discontinuity` handling). A larger batch still means
# fewer bounded transport reconnections and coarser bound-checking
# granularity between batches, and slower operator-marker rescue:
# `_refresh_markers` can only discover a marker at a batch boundary, so a
# batch's worth of frames is roughly the worst-case rescue-buffer depth
# needed (see `CaptureBounds.adjacent_context_frame_count`, max 16). 12
# keeps one batch comfortably within that ceiling with headroom, while
# still being meaningfully less choppy than one-frame-at-a-time polling (12
# frames at a 2 fps nominal source is ~6 real seconds between checkpoints).
MAX_PLANE_CACHE = 4
_ERROR_EXIT_CODES = {
    "unsafe_output_path": 6, "nonempty_output_directory": 7, "invalid_camera_node_config": 6,
    "invalid_frame_driven_configuration": 6, "onnx_cuda_unavailable": 10, "onnx_cuda_no_fallback": 10,
    "onnx_cuda_session_load_failed": 11, "onnx_cuda_inference_failed": 12, "onnx_cuda_mixed_execution": 13,
    "onnx_cuda_verification_insufficient": 14,
}


def _capture_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one bounded reviewed temporal capture against a paired Camera Node.")
    parser.add_argument("--camera-node-config", required=True, type=Path, help="Ignored local JSON: base_address/credential/camera_id/stream_id/evidence_profile_id.")
    parser.add_argument("--provider", required=True, choices=("frame-driven-onnx-cuda",))
    parser.add_argument("--provider-config", required=True, type=Path, help="Existing frame-driven provider configuration JSON.")
    parser.add_argument("--output", required=True, type=Path, help="New or empty output directory.")
    parser.add_argument("--duration", type=int, default=120, help="Bounded capture duration in seconds.")
    parser.add_argument("--review-score-threshold", type=float, default=0.02, help="Low detector threshold used only for review capture, never a deployed default.")
    parser.add_argument("--shadow-operating-point", type=float, default=0.5, help="Current shadow-deployed operating threshold, for trigger classification only.")
    parser.add_argument("--review-floor", type=float, default=0.05, help="Lower review floor for below-operating-point retention.")
    parser.add_argument("--max-analysis-frames", type=int, default=CaptureBounds().max_analysis_frames)
    parser.add_argument("--max-bytes-stored", type=int, default=CaptureBounds().max_bytes_stored)
    parser.add_argument("--max-high-resolution-frames", type=int, default=CaptureBounds().max_high_resolution_frames)
    parser.add_argument("--privacy-ignore-region", action="append", default=[], metavar="LEFT,TOP,RIGHT,BOTTOM", help="Repeatable normalized Privacy/Ignore box.")
    parser.add_argument(
        "--retain-exact-analysis",
        action="store_true",
        help=(
            "Retain a bounded diagnostic envelope binding each retained analysis frame to "
            "its detector outputs, model provenance, geometry attribution, and lineage. "
            "Default off; creates neither truth nor a product record."
        ),
    )
    parser.add_argument(
        "--validation-burst", action="store_true",
        help="Explicitly request one labeled engineering high-resolution burst at session start to validate the "
             "burst endpoint end-to-end, independent of any real detector/tracker trigger. Never represents wildlife.",
    )
    parser.add_argument(
        "--scene-id", required=True,
        help="Stable physical-scene identity this session belongs to (e.g. 'feeder-close', 'lawn-north', "
             "'woods-tree-line'). One materially distinct camera view/environment -- never inferred from a small "
             "camera nudge. Lowercase letters/digits/hyphens only. See docs/wildlife-detector-training-contract.md.",
    )
    parser.add_argument(
        "--capture-purpose", choices=CAPTURE_PURPOSES, default=CAPTURE_PURPOSE_TRAINING_CANDIDATE,
        help="training_candidate (default): this session's frames may later become training/local-validation "
             "candidates. holdout_v2_candidate: reserve every frame this session retains -- structurally excluding "
             "it from training/local-validation selection (see mockingbird.training.wildlife_multiscene) -- for "
             "genuinely independent future promotion-quality evaluation. Does not by itself label anything; it "
             "only marks provenance.",
    )
    return parser


def _mark_parser() -> argparse.ArgumentParser:
    from mockingbird.observation.temporal_capture import OPERATOR_MARKER_KINDS
    parser = argparse.ArgumentParser(description="Write one timestamped engineering operator marker into a running capture directory.")
    parser.add_argument("--capture", required=True, type=Path, help="Existing capture output directory.")
    parser.add_argument("--kind", required=True, choices=OPERATOR_MARKER_KINDS)
    parser.add_argument("--note", default="")
    parser.add_argument("--lookback-seconds", type=int, default=20)
    return parser


def _parse_region(value: str) -> tuple[float, float, float, float]:
    parts = value.split(",")
    if len(parts) != 4:
        raise TemporalCaptureError("invalid_privacy_ignore_region")
    return tuple(float(item) for item in parts)  # type: ignore[return-value]


def run_mark(argv: list[str] | None = None) -> int:
    args = _mark_parser().parse_args(argv)
    try:
        marker = OperatorMarker(
            marker_id=f"marker-{uuid4().hex[:16]}", kind=args.kind,
            host_time_iso=datetime.now(UTC).isoformat(), note=args.note, lookback_seconds=args.lookback_seconds,
        )
        path = write_operator_marker(args.capture, marker)
        print(f"Operator marker written to {path}.")
        return 0
    except TemporalCaptureError as error:
        print(f"Operator marker rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error), 2)


def _decode_plane_from_bytes(payload: bytes, *, comparison_width: int, comparison_height: int):
    from io import BytesIO
    try:
        from PIL import Image
        with Image.open(BytesIO(payload)) as source:
            source.load()
            grayscale = source.convert("L").resize((comparison_width, comparison_height), Image.Resampling.BILINEAR)
            pixels = list(grayscale.getdata())
    except Exception as error:
        raise TemporalCaptureError("undecodable_frame") from error
    return tuple(tuple(pixels[row * comparison_width:(row + 1) * comparison_width]) for row in range(comparison_height))


class _CaptureLoop:
    """Bounded, checkpointed orchestration built entirely from already-
    established components: `LiveCameraNodeShadowSession` (Stage 5, reused
    unchanged), `motion_proposal_strategy.generate_proposals` (Stage 6.5,
    reused unchanged), and the pure Stage 6.6 trigger/bounds contract. This
    class only decides retention and enforces bounds; it never re-implements
    the Node transport, detector, or tracker."""

    def __init__(self, *, session: LiveCameraNodeShadowSession, output_directory: Path, bounds: CaptureBounds,
                 shadow_operating_point: float, review_floor: float, privacy_regions: tuple[tuple[float, float, float, float], ...],
                 retain_exact_analysis: bool = False, model_fingerprint: str = "unknown",
                 provider_id: str = "unknown", capture_score_threshold: float = 0.02,
                 holdout_v2_session: bool = False, scene_id: str = "") -> None:
        self.session = session
        self.output_directory = output_directory
        self.bounds = bounds
        self.shadow_operating_point = shadow_operating_point
        self.review_floor = review_floor
        self.privacy_regions = privacy_regions
        self.retain_exact_analysis = retain_exact_analysis
        self.model_fingerprint = model_fingerprint
        self.provider_id = provider_id
        self.capture_score_threshold = capture_score_threshold
        # Stage-3 Holdout v2 groundwork: session-level, operator-set, and
        # otherwise inert -- see `RetainedFrameRecord.holdout_v2_candidate`.
        self.holdout_v2_session = holdout_v2_session
        # Multi-Scene Backyard Domain Acquisition v1: session-level,
        # operator-set physical-scene identity -- see `RetainedFrameRecord.
        # scene_id`. Every frame this loop retains inherits the same value.
        self.scene_id = scene_id
        # Set from outside this loop's own async `run()` (a signal handler
        # registered by `_run_capture`) to request a clean early stop -- see
        # `request_stop`. Checked first, every iteration of `run()`'s own
        # while loop, so it takes effect at the next natural checkpoint
        # rather than interrupting an in-flight batch mid-frame.
        self.stop_requested = False
        self.retained: list[RetainedFrameRecord] = []
        self.markers_seen: dict[str, OperatorMarker] = {}
        self.pretrigger: deque = deque(maxlen=max(1, bounds.pretrigger_frame_count))
        self.post_trigger_remaining = 0
        self.periodic = PeriodicNegativeScheduler(interval_seconds=bounds.periodic_negative_interval_seconds, max_samples=bounds.max_periodic_negative_samples)
        self.recurring = RecurringGeometryTracker()
        self.bytes_written = 0
        self.plane_cache: dict[str, object] = {}
        # Deliberately unbounded deque: eviction is driven entirely by the
        # explicit `while` loop in `_plane`, which removes from both
        # `plane_order` and `plane_cache` together. A `maxlen` deque would
        # silently drop the oldest id here without ever removing its (much
        # larger) decoded-plane entry from `plane_cache`, leaking memory.
        self.plane_order: deque = deque()
        # Retroactive operator-marker rescue buffer: frames processed with
        # no trigger of their own, kept around so a marker discovered on a
        # *later* batch boundary can still retroactively retain the frame
        # it actually refers to (see `_refresh_markers`). Bounded by the
        # `adjacent_context_frame_count` ceiling; maxlen=0 (allowed by that
        # bound's own 0-16 range) simply disables rescue.
        self.recent_frames: deque = deque(maxlen=bounds.adjacent_context_frame_count)
        # Companion bound for the opposite case: a frame that already
        # qualified for retention through its own unrelated trigger (a real
        # detection, recurring static geometry, a shadow-track event, ...)
        # never enters `recent_frames` above, so a marker discovered on a
        # later batch boundary that refers back to it would otherwise never
        # be able to find it. Confirmed missing on real daylight hardware:
        # a busy scene retains almost every frame for an unrelated reason,
        # so the trigger-less rescue pool above stays near-empty and every
        # operator marker's `operator_marker_ids` backfill silently no-ops.
        # Holds only `(frame_id, received_at)` -- enough identity to find
        # and replace the existing retained record in place, never enough
        # to duplicate a `_retain` call (see `_refresh_markers`). Bounded by
        # the same ceiling as `recent_frames` for the same reason: one
        # batch's worth of frames is the worst-case depth needed between
        # marker-discovery checkpoints.
        self.recent_retained_identities: deque = deque(maxlen=bounds.adjacent_context_frame_count)
        self.last_frame_id: str | None = None
        self.last_source_offset_ms: int | None = None
        self.last_generation: str | None = None
        self.generation_reset_count = 0
        self.provider_generations: list[str] = []
        self.stop_condition = STOP_STREAM_ENDED
        self.analysis_width = 1
        self.analysis_height = 1

    def _plane(self, frame_id: str, payload: bytes):
        if frame_id not in self.plane_cache:
            plane = _decode_plane_from_bytes(
                payload, comparison_width=FULL_FRAME_PLUS_MOTION_PROPOSALS.comparison_width,
                comparison_height=FULL_FRAME_PLUS_MOTION_PROPOSALS.comparison_height,
            )
            self.plane_cache[frame_id] = plane
            self.plane_order.append(frame_id)
            while len(self.plane_order) > MAX_PLANE_CACHE:
                stale = self.plane_order.popleft()
                self.plane_cache.pop(stale, None)
        return self.plane_cache[frame_id]

    def _bounds_exceeded(self) -> str | None:
        if len(self.retained) >= self.bounds.max_analysis_frames:
            return STOP_FRAME_LIMIT
        if self.bytes_written >= self.bounds.max_bytes_stored:
            return STOP_BYTE_LIMIT
        if sum(1 for item in self.retained if item.high_resolution) >= self.bounds.max_high_resolution_frames:
            return STOP_HIGH_RESOLUTION_LIMIT
        if len(self.markers_seen) >= self.bounds.max_operator_markers:
            return STOP_MARKER_LIMIT
        if self.session.provider.active_track_count > self.bounds.max_active_tracks:
            return STOP_ACTIVE_TRACK_LIMIT
        return None

    def _refresh_markers(self) -> None:
        discovered = False
        for marker in read_operator_markers(self.output_directory):
            if marker.marker_id not in self.markers_seen:
                discovered = True
            self.markers_seen[marker.marker_id] = marker
        if not discovered or not self.markers_seen:
            return
        # A marker only ever matches a frame received at-or-before the
        # marker's own timestamp (see `markers_near`), but this method only
        # ever runs *before* fetching new (i.e. future) frames -- so a
        # marker just discovered here can never match anything we are
        # about to receive. It can only match frames already sitting in
        # `recent_frames` from earlier, undertriggered batches. Rescan them
        # now that the marker is known.
        markers = tuple(self.markers_seen.values())
        for frame, detection_boxes, track_generation_ids, proposal_boxes, exact_analysis in list(self.recent_frames):
            if frame.received_at is None:
                continue
            near = markers_near(markers, host_time_iso=frame.received_at.isoformat(), default_lookback_seconds=20)
            if not near:
                continue
            self._retain(
                frame, [TRIGGER_OPERATOR_MARKER], detection_boxes, track_generation_ids, proposal_boxes,
                marker_ids=tuple(item.marker_id for item in near),
                exact_analysis=exact_analysis,
            )
            self.post_trigger_remaining = self.bounds.post_trigger_frame_count

        # The mirror case: a frame that already retained itself for an
        # unrelated trigger. `_retain` would silently no-op on its own
        # frame_id-dedup guard (dropping the marker id on the floor), so
        # backfill the existing record in place instead.
        for frame_id, received_at in self.recent_retained_identities:
            if received_at is None:
                continue
            near = markers_near(markers, host_time_iso=received_at.isoformat(), default_lookback_seconds=20)
            if not near:
                continue
            for index, record in enumerate(self.retained):
                if record.frame_id != frame_id:
                    continue
                merged_marker_ids = tuple(dict.fromkeys((*record.operator_marker_ids, *(item.marker_id for item in near))))
                if merged_marker_ids == record.operator_marker_ids:
                    break
                merged_triggers = tuple(dict.fromkeys((*record.trigger_reasons, TRIGGER_OPERATOR_MARKER)))
                self.retained[index] = replace(record, operator_marker_ids=merged_marker_ids, trigger_reasons=merged_triggers)
                break

    def request_stop(self) -> None:
        """Request a clean early stop at the next loop checkpoint (see
        `run`'s first check below). Safe to call from a signal handler:
        this only ever sets a plain attribute, never touches the network,
        filesystem, or any asyncio primitive directly."""

        self.stop_requested = True

    async def run(self, *, started_wall: datetime, duration_seconds: int) -> str:
        while True:
            if self.stop_requested:
                return STOP_MANUAL
            elapsed = (datetime.now(UTC) - started_wall).total_seconds()
            if elapsed >= duration_seconds:
                return STOP_DURATION_ELAPSED
            exceeded = self._bounds_exceeded()
            if exceeded is not None:
                return exceeded
            remaining_frames = self.bounds.max_analysis_frames - len(self.retained)
            batch = max(1, min(BATCH_FRAMES, remaining_frames))
            self._refresh_markers()
            try:
                results = await self.session.run(maximum_frames=batch)
            except (CameraNodeClientError, ValueError):
                # Stage 6.11B: an ordinary HTTP reconnect -- a fresh
                # transport connection under the same provider_generation,
                # the Node's per-connection sequence header restarting at 1
                # -- no longer raises here at all. `CameraNodeAnalysisSource`
                # recognizes the new connection segment and keeps its
                # sequence/offset bookkeeping consistent across it, and
                # `FrameDrivenObservationProvider.observe_live_frame`
                # classifies the boundary through the same Stage 6.11
                # decision contract `replay_frames` already uses, bridging
                # the live tracker across it rather than requiring this loop
                # to rebuild the source and restart the whole tracker
                # generation on every batch boundary (the removed Stage
                # 6.6-era recovery this replaces -- see
                # docs/reconnect-continuity-contract.md). Anything that
                # still reaches this handler is a genuine unrecoverable
                # transport/source error: reported honestly as a stop, never
                # silently retried.
                return STOP_TRANSPORT_ERROR
            if not results:
                return STOP_STREAM_ENDED
            for result in results:
                self._process_result(result)
            exceeded = self._bounds_exceeded()
            if exceeded is not None:
                return exceeded

    def _process_result(self, result) -> None:
        if not result.frame_packets:
            return
        frame = result.frame_packets[0]
        if frame.width and frame.height:
            self.analysis_width, self.analysis_height = frame.width, frame.height
        generation = frame.provider_generation or "unknown"
        if generation not in self.provider_generations:
            self.provider_generations.append(generation)
        discontinuity = self.last_generation is not None and generation != self.last_generation
        if discontinuity:
            self.generation_reset_count += 1
            self.pretrigger.clear()
            self.plane_cache.clear()
            self.plane_order.clear()
            self.last_frame_id = None
        self.last_generation = generation

        detections = tuple(item for item in result.detection_observations if item.is_animal)
        triggers = list(classify_detection_triggers(detections, operating_point=self.shadow_operating_point, review_floor=self.review_floor))
        if has_track_event(result.track_updates):
            from mockingbird.observation.temporal_capture import TRIGGER_SHADOW_TRACK_EVENT
            triggers.append(TRIGGER_SHADOW_TRACK_EVENT)
        if any(item.role == "high_resolution_burst" for item in result.evidence_candidates):
            triggers.append(TRIGGER_HIGH_RESOLUTION_BURST)

        marker_ids: tuple[str, ...] = ()
        if self.markers_seen and frame.received_at is not None:
            near = markers_near(tuple(self.markers_seen.values()), host_time_iso=frame.received_at.isoformat(), default_lookback_seconds=20)
            if near:
                triggers.append(TRIGGER_OPERATOR_MARKER)
                marker_ids = tuple(item.marker_id for item in near)

        proposal_boxes: tuple[tuple[float, float, float, float], ...] = ()
        if frame.payload is not None and frame.frame_id is not None and not discontinuity and self.last_frame_id is not None:
            try:
                current_plane = self._plane(frame.frame_id, frame.payload)
                predecessor_plane = self.plane_cache.get(self.last_frame_id)
                if predecessor_plane is not None:
                    proposal_result = generate_proposals(
                        FULL_FRAME_PLUS_MOTION_PROPOSALS,
                        current=FrameIdentity(frame.frame_id, "live", frame.source_offset_ms, provider_generation=generation),
                        predecessor=FrameIdentity(self.last_frame_id, "live", self.last_source_offset_ms, provider_generation=generation),
                        predecessor_plane=predecessor_plane, current_plane=current_plane,
                        excluded_regions=self.privacy_regions,
                    )
                    if proposal_result.proposals:
                        triggers.append(TRIGGER_MOTION_PROPOSAL_GENERATED)
                        proposal_boxes = tuple(item.window.source_box for item in proposal_result.proposals)
            except TemporalCaptureError:
                pass
        elif frame.payload is not None and frame.frame_id is not None:
            self._plane(frame.frame_id, frame.payload)

        privacy_interaction = False
        if self.privacy_regions:
            for update in result.track_updates:
                if update.bounding_box is not None and _near_any_region(update.bounding_box, self.privacy_regions):
                    privacy_interaction = True
                    triggers.append(TRIGGER_PRIVACY_IGNORE_INTERACTION)
                    break

        recurring_hit = False
        for item in detections:
            if item.bounding_box is not None and self.recurring.observe(item.bounding_box):
                recurring_hit = True
        if recurring_hit:
            triggers.append(TRIGGER_RECURRING_STATIC_GEOMETRY)

        if discontinuity:
            triggers.append(TRIGGER_GENERATION_OR_SEQUENCE_DISCONTINUITY)

        periodic_hit = False
        # Use the host receive clock, not frame.source_offset_ms: the
        # latter is zeroed against each transport connection's first frame
        # (see the reconnect handling in `run()`), so on real hardware --
        # where a fresh connection, and therefore a fresh zero point, is
        # the normal outcome of every batch boundary -- it rarely climbs
        # far enough within one connection's lifetime to ever cross
        # `periodic_negative_interval_seconds`. received_at is a plain host
        # wall-clock timestamp untouched by reconnects, so elapsed time
        # keeps accumulating across the whole bounded session.
        if frame.received_at is not None:
            received_at_ms = int(frame.received_at.timestamp() * 1000)
            if not triggers and self.periodic.due(received_at_ms):
                from mockingbird.observation.temporal_capture import TRIGGER_PERIODIC_NEGATIVE_SAMPLE
                triggers.append(TRIGGER_PERIODIC_NEGATIVE_SAMPLE)
                periodic_hit = True

        retained_now = bool(triggers) or self.post_trigger_remaining > 0
        pretrigger_flush: list = []
        if triggers and not periodic_hit:
            pretrigger_flush = list(self.pretrigger)
            self.post_trigger_remaining = self.bounds.post_trigger_frame_count
        elif self.post_trigger_remaining > 0:
            triggers = [TRIGGER_POST_TRIGGER_CONTEXT]
            self.post_trigger_remaining -= 1

        track_generation_ids = tuple({item.generation_id for item in result.track_updates})
        detection_boxes = tuple(
            (*item.bounding_box, round(item.confidence or 0.0, 3)) for item in detections if item.bounding_box is not None
        )
        exact_analysis = None
        if self.retain_exact_analysis:
            from mockingbird.observation.exact_frame_capture import build_exact_analysis_frame

            exact_analysis = build_exact_analysis_frame(
                frame,
                result.detection_observations,
                result.track_updates,
                model_fingerprint=self.model_fingerprint,
                provider_id=self.provider_id,
                capture_score_threshold=self.capture_score_threshold,
            ).to_semantic_dict()
        for context_frame, context_triggers, context_exact_analysis in pretrigger_flush:
            self._retain(
                context_frame,
                list(context_triggers) + [TRIGGER_PRETRIGGER_CONTEXT],
                (),
                (),
                (),
                exact_analysis=context_exact_analysis,
            )
        if retained_now:
            self._retain(
                frame, triggers, detection_boxes, track_generation_ids,
                proposal_boxes, marker_ids=marker_ids,
                # This retains the low-resolution analysis-stream frame that
                # triggered the burst, never the burst's own image -- it is
                # never itself high-resolution. `TRIGGER_HIGH_RESOLUTION_BURST`
                # stays in its own trigger_reasons above so a reviewer can
                # still see that a burst correlates with this moment; the
                # real high-resolution evidence is retained separately below,
                # once per captured burst, by `_retain_high_resolution_evidence`.
                high_resolution=False, privacy_interaction=privacy_interaction,
                exact_analysis=exact_analysis,
            )
            if frame.frame_id is not None and frame.received_at is not None:
                self.recent_retained_identities.append((frame.frame_id, frame.received_at))
        else:
            self.pretrigger.append((frame, tuple(triggers), exact_analysis))
            # No trigger fired for this frame yet -- but an operator marker
            # written moments from now, correlating backward to right about
            # this frame's own received_at, would only ever be discovered
            # at the *next* batch boundary (see `_refresh_markers`), by
            # which point new frames are already in the future relative to
            # that marker. Keep it rescue-eligible until it ages out.
            self.recent_frames.append((frame, detection_boxes, track_generation_ids, proposal_boxes, exact_analysis))

        # One dedicated high-resolution record per captured burst, never
        # collapsed onto the single low-resolution trigger frame above: two
        # simultaneous meaningful track updates on this same processed frame
        # can each independently win their own scheduler-issued, Camera-
        # Node-captured burst, and each is genuinely separate high-
        # resolution evidence with its own real image bytes.
        for candidate in result.evidence_candidates:
            if candidate.role == "high_resolution_burst":
                self._retain_high_resolution_evidence(candidate, frame=frame, provider_generation=generation)

        if frame.frame_id is not None:
            self.last_frame_id = frame.frame_id
            self.last_source_offset_ms = frame.source_offset_ms

    def _retain(self, frame, triggers, detection_boxes, track_generation_ids, proposal_boxes, *, marker_ids=(), high_resolution=False, privacy_interaction=False, exact_analysis=None) -> None:
        if frame.frame_id is None or frame.payload is None or frame.source_offset_ms is None:
            return
        if any(item.frame_id == frame.frame_id for item in self.retained):
            return
        write_frame_bytes(self.output_directory, frame_id=frame.frame_id, payload=frame.payload, high_resolution=high_resolution)
        self.bytes_written += len(frame.payload)
        record = RetainedFrameRecord(
            frame_id=frame.frame_id, sequence=frame.frame_sequence or len(self.retained),
            source_offset_ms=frame.source_offset_ms, provider_generation=frame.provider_generation or "unknown",
            content_hash=sha256(frame.payload).hexdigest(), byte_size=len(frame.payload),
            trigger_reasons=tuple(dict.fromkeys(triggers)), detector_observation_count=len(detection_boxes),
            animal_detection_count=len(detection_boxes),
            max_animal_score=max((item[4] for item in detection_boxes), default=None),
            active_track_count=len(track_generation_ids), motion_proposal_count=len(proposal_boxes),
            high_resolution=high_resolution, privacy_ignore_interaction=privacy_interaction,
            operator_marker_ids=marker_ids, detection_boxes=detection_boxes,
            motion_proposal_boxes=proposal_boxes, track_generation_ids=track_generation_ids,
            exact_analysis=exact_analysis,
            # Session-level, operator-set constant -- every frame this loop
            # retains inherits the same reservation; see `RetainedFrameRecord.
            # holdout_v2_candidate` and `--capture-purpose`.
            holdout_v2_candidate=self.holdout_v2_session,
            scene_id=self.scene_id,
            # Stage 6.8 source-local provenance the reconnect-safe session
            # timeline is derived from: the real per-connection Node session
            # id (already flowing through on every analysis-stream frame,
            # just never previously recorded here) and the host wall-clock
            # instant this frame was actually received. `attach_session_
            # timeline` fills in the derived session_*/connection_segment_*/
            # temporal_* fields once, after the whole session finishes (see
            # `_run_capture`).
            host_received_at=frame.received_at.isoformat() if frame.received_at is not None else "",
            source_capture_timestamp=frame.captured_at.isoformat() if frame.captured_at is not None else None,
            connection_segment_id=frame.node_session_id or "",
        )
        self.retained.append(record)

    def _retain_high_resolution_evidence(self, candidate: EvidenceCandidate, *, frame, provider_generation: str) -> None:
        """Retain one captured evidence-burst's own real image as its own
        record -- never folded into the low-resolution trigger frame's
        boolean flag (see `_retain`'s `high_resolution=False` above).

        `EvidenceCandidate` carries no payload of its own (it is a
        provider-neutral fact record); the real bytes `request_evidence_
        burst` already fetched from the Camera Node live only in the
        session's own bounded `temporary_burst_payload` cache, keyed by the
        `content_hash` quality fact every `high_resolution_burst` candidate
        carries (see `LiveCameraNodeShadowSession._process_frame`). A
        content hash this session can no longer resolve -- already evicted
        from that bounded cache, or a session type that does not expose the
        lookup at all -- is skipped rather than substituting unrelated
        bytes: honest omission, never a mislabeled duplicate.
        """
        facts = dict(candidate.quality_facts)
        content_hash = facts.get("content_hash")
        if not isinstance(content_hash, str) or not content_hash:
            return
        fetch = getattr(self.session, "temporary_burst_payload", None)
        payload = fetch(content_hash) if callable(fetch) else None
        if not payload:
            return
        frame_id = f"burst-{content_hash[:16]}"
        if any(item.frame_id == frame_id for item in self.retained):
            return
        write_frame_bytes(self.output_directory, frame_id=frame_id, payload=payload, high_resolution=True)
        self.bytes_written += len(payload)
        track_generation_ids = (candidate.track_generation_id,) if candidate.track_generation_id else ()
        self.retained.append(RetainedFrameRecord(
            frame_id=frame_id, sequence=frame.frame_sequence or len(self.retained),
            source_offset_ms=frame.source_offset_ms or 0, provider_generation=provider_generation,
            content_hash=sha256(payload).hexdigest(), byte_size=len(payload),
            trigger_reasons=(TRIGGER_HIGH_RESOLUTION_BURST,), detector_observation_count=0,
            animal_detection_count=0, max_animal_score=None,
            active_track_count=len(track_generation_ids), motion_proposal_count=0,
            high_resolution=True, track_generation_ids=track_generation_ids,
            host_received_at=frame.received_at.isoformat() if frame.received_at is not None else "",
            source_capture_timestamp=candidate.captured_at.isoformat() if candidate.captured_at is not None else None,
            connection_segment_id=frame.node_session_id or "",
            holdout_v2_candidate=self.holdout_v2_session,
            scene_id=self.scene_id,
        ))


def _tracker_proposal_config_fingerprint(configuration: FrameDrivenProviderConfiguration) -> str:
    """One deterministic fingerprint covering both the tracker settings and
    the reused Stage 6.5 motion-proposal strategy config, reusing the same
    `semantic_fingerprint` convention every other benchmark report uses."""

    from dataclasses import asdict
    from mockingbird.observation.replay import semantic_fingerprint

    return semantic_fingerprint({
        "tracker_settings": asdict(configuration.settings),
        "motion_proposal_strategy": asdict(FULL_FRAME_PLUS_MOTION_PROPOSALS),
    })


def _near_any_region(box: tuple[float, float, float, float], regions: tuple[tuple[float, float, float, float], ...], *, margin: float = 0.08) -> bool:
    left, top, right, bottom = box
    centroid = ((left + right) / 2.0, (top + bottom) / 2.0)
    for region_left, region_top, region_right, region_bottom in regions:
        if (region_left - margin) <= centroid[0] <= (region_right + margin) and (region_top - margin) <= centroid[1] <= (region_bottom + margin):
            return True
    return False


def _request_validation_burst(session: LiveCameraNodeShadowSession, loop: "_CaptureLoop", connection, *, started_wall: datetime) -> None:
    """Fire exactly one explicitly-labeled engineering burst request at
    session start, independent of any real detector/tracker trigger. Proves
    the real `/evidence-burst` endpoint works end-to-end even on a quiet
    (for example nighttime) scene where no genuine track ever confirms.
    Never represents wildlife -- the retained frame_id is prefixed
    `validation-burst-` and carries only the `high_resolution_burst`
    trigger, exactly like any other burst capture.

    Routed through the same Stage 6.9 scheduler as every other burst
    opportunity (as `engineering_validation_request=True`) so this explicit
    engineering path is recorded in scheduler diagnostics/history rather than
    bypassing it entirely; a fresh session's reserved override allowance
    always has room for this one bounded request."""

    from mockingbird.observation.burst_scheduler import BurstOpportunity
    from mockingbird.observation.media_contracts import EvidenceBurstRequest

    opportunity = BurstOpportunity(
        opportunity_id=f"validation-burst-opportunity:{started_wall.isoformat()}",
        stream_id=connection.stream_id, session_id=session.scheduler.session_id,
        track_generation_id="validation-burst", trigger_frame_id="validation-burst-trigger",
        source_offset_ms=0, broad_class="animal", provider_generation=None,
        trigger_reason="engineering_validation", requested_evidence_profile=connection.evidence_profile_id,
        engineering_validation_request=True,
    )
    decision = session.scheduler.decide(opportunity)
    print(f"Validation burst opportunity {opportunity.opportunity_id}: scheduler outcome={decision.outcome}")
    if not decision.should_issue:
        return
    request_id = decision.request_id
    request = EvidenceBurstRequest(
        request_id=request_id, stream_id=connection.stream_id, node_session_id="validation-burst-session",
        track_generation_id="validation-burst", trigger_frame_id="validation-burst-trigger",
        trigger_captured_at=started_wall, requested_frame_count=1, requested_profile_id=connection.evidence_profile_id,
        cadence_ms=0, subject_geometry=None, zone_id=None, deadline_at=started_wall + timedelta(seconds=15),
    )
    result = session.transport.request_evidence_burst(request)
    print(f"Validation burst request {request_id}: status={result.status} failure_code={result.failure_code}")
    if result.status != "captured" or not result.frames:
        session.scheduler.record_result(request_id, status="failed" if result.status == "failed" else "stale", failure_code=result.failure_code)
        return
    session.scheduler.record_result(
        request_id, status="captured", byte_size=len(result.frames[0].payload), latency_ms=result.frames[0].request_to_capture_ms,
    )
    frame = result.frames[0]
    frame_id = f"validation-burst-{frame.content_hash[:16]}"
    from mockingbird.observation.temporal_capture import TRIGGER_HIGH_RESOLUTION_BURST as _TRIGGER
    write_frame_bytes(loop.output_directory, frame_id=frame_id, payload=frame.payload, high_resolution=True)
    loop.bytes_written += len(frame.payload)
    loop.retained.append(RetainedFrameRecord(
        frame_id=frame_id, sequence=0, source_offset_ms=0, provider_generation=frame.provider_generation,
        content_hash=frame.content_hash, byte_size=len(frame.payload), trigger_reasons=(_TRIGGER,),
        detector_observation_count=0, animal_detection_count=0, max_animal_score=None, active_track_count=0,
        motion_proposal_count=0, high_resolution=True,
        # This one-off `/evidence-burst` request is not part of the main
        # analysis-stream connection sequence, so it gets its own fixed,
        # deterministic pseudo-segment rather than borrowing the first real
        # connection's identity it has nothing genuinely in common with.
        host_received_at=datetime.now(UTC).isoformat(),
        source_capture_timestamp=frame.captured_at.isoformat(),
        connection_segment_id="validation-burst",
        scene_id=loop.scene_id,
    ))


async def _run_capture(args: argparse.Namespace) -> int:
    # Fail fast, before opening any Camera Node connection: an operator
    # typo in --scene-id should never cost a real bounded field session.
    if not args.scene_id or not SCENE_ID_PATTERN.fullmatch(args.scene_id):
        raise TemporalCaptureError("invalid_scene_id")
    connection = load_camera_node_connection_config(args.camera_node_config)
    configuration = FrameDrivenProviderConfiguration.load(args.provider_config)
    bundle = OnnxModelBundle.load(configuration.model_bundle_path)
    review_bundle = replace(bundle, score_threshold=args.review_score_threshold)
    detector = OnnxCudaObservationProvider(bundle=review_bundle)
    provider = FrameDrivenObservationProvider(detector=detector, settings=configuration.settings)
    provider.load()

    output_directory = safe_capture_output_directory(args.output)
    privacy_regions = tuple(_parse_region(item) for item in args.privacy_ignore_region)
    bounds = CaptureBounds(
        max_duration_seconds=args.duration, max_analysis_frames=args.max_analysis_frames,
        max_bytes_stored=args.max_bytes_stored, max_high_resolution_frames=args.max_high_resolution_frames,
    )

    source = CameraNodeAnalysisSource(connection.stream_id, analysis_excluded_regions=privacy_regions)
    transport = CameraNodeHttpTransport(
        base_address=connection.base_address, credential=connection.credential, camera_id=connection.camera_id,
        stream_id=connection.stream_id, evidence_profile_id=connection.evidence_profile_id,
    )
    session = LiveCameraNodeShadowSession(source=source, transport=transport, provider=provider, evidence_profile_id=connection.evidence_profile_id)

    loop = _CaptureLoop(
        session=session, output_directory=output_directory, bounds=bounds,
        shadow_operating_point=args.shadow_operating_point, review_floor=args.review_floor, privacy_regions=privacy_regions,
        retain_exact_analysis=args.retain_exact_analysis, model_fingerprint=bundle.fingerprint,
        provider_id=provider.provider_id, capture_score_threshold=args.review_score_threshold,
        holdout_v2_session=(args.capture_purpose == CAPTURE_PURPOSE_HOLDOUT_V2_CANDIDATE),
        scene_id=args.scene_id,
    )
    started_wall = datetime.now(UTC)
    node_session_id = f"temporal-capture:{uuid4().hex[:16]}"

    # A running capture is a bounded foreground command, not a daemon -- but
    # an operator doing real multi-scene fieldwork legitimately wants to end
    # a session early once a scene has been covered, without losing the
    # manifest for whatever was already retained. One Ctrl-C (SIGINT) or
    # SIGTERM now requests a clean stop at the loop's own next checkpoint
    # (`STOP_MANUAL`, already a validated stop condition -- see
    # `_CaptureLoop.request_stop`) instead of raising KeyboardInterrupt
    # straight through this function and skipping manifest assembly below
    # entirely. Falls back to duration/resource bounds only, unchanged,
    # wherever the running event loop cannot register a signal handler.
    import asyncio

    running_loop = asyncio.get_running_loop()
    registered_signals: list[signal.Signals] = []
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            running_loop.add_signal_handler(sig, loop.request_stop)
            registered_signals.append(sig)
        except (NotImplementedError, RuntimeError):
            pass
    try:
        session.start()
        if args.validation_burst:
            _request_validation_burst(session, loop, connection, started_wall=started_wall)
        stop_condition = await loop.run(started_wall=started_wall, duration_seconds=args.duration)
    finally:
        for sig in registered_signals:
            running_loop.remove_signal_handler(sig)
        session.stop()
        provider.close()
    ended_wall = datetime.now(UTC)

    config = CaptureSessionConfig(
        schema_version=CAPTURE_MANIFEST_SCHEMA_VERSION, capture_version="temporal-capture-session-v1", stream_id=connection.stream_id,
        transport_key="camera-node-http-multipart-jpeg", provider_key=provider.provider_id,
        analysis_width=loop.analysis_width, analysis_height=loop.analysis_height, nominal_fps=configuration.settings.source_nominal_fps,
        review_score_threshold=args.review_score_threshold, shadow_operating_point=args.shadow_operating_point,
        review_floor=args.review_floor, evidence_profile_id=connection.evidence_profile_id, bounds=bounds,
        privacy_ignore_regions=privacy_regions,
        exact_analysis_capture_enabled=args.retain_exact_analysis,
        scene_id=args.scene_id, capture_purpose=args.capture_purpose,
    )
    session_id = f"temporal-capture-{started_wall.strftime('%Y%m%dT%H%M%SZ')}"

    # Stage 6.8: derive the reconnect-safe session timeline once, over the
    # complete retained-frame set, then run one final honest marker-
    # correlation pass over the whole session (not just the bounded live
    # rescue buffers `_CaptureLoop` used while capture was still running) --
    # now that every frame carries a real host receive timestamp, a marker
    # can backfill onto any already-retained frame regardless of which
    # connection segment produced it.
    timelined_frames, session_timeline = attach_session_timeline(tuple(loop.retained), session_id=session_id)
    markers = tuple(loop.markers_seen.values())
    if markers:
        associations = correlate_markers_to_frames(
            tuple(
                {"frame_id": item.frame_id, "host_received_at": item.host_received_at, "operator_marker_ids": item.operator_marker_ids}
                for item in timelined_frames
            ),
            markers,
        )
        timelined_frames = tuple(
            replace(item, operator_marker_ids=associations.get(item.frame_id, item.operator_marker_ids))
            for item in timelined_frames
        )

    manifest = CaptureSessionManifest(
        config=config, session_id=session_id,
        node_session_id=node_session_id, start_host_time_iso=started_wall.isoformat(), end_host_time_iso=ended_wall.isoformat(),
        start_source_offset_ms=loop.retained[0].source_offset_ms if loop.retained else 0,
        end_source_offset_ms=loop.retained[-1].source_offset_ms if loop.retained else 0,
        first_sequence=loop.retained[0].sequence if loop.retained else 0, last_sequence=loop.retained[-1].sequence if loop.retained else 0,
        sequence_gap_count=source.status().sequence_gaps, dropped_frame_count=source.status().dropped_frames,
        coalesced_frame_count=source.status().coalesced_frames, stale_frame_count=source.status().stale_frames,
        generation_reset_count=loop.generation_reset_count, provider_generations=tuple(loop.provider_generations),
        model_fingerprint=bundle.fingerprint,
        tracker_proposal_config_fingerprint=_tracker_proposal_config_fingerprint(configuration),
        frames=timelined_frames, operator_markers=markers, stop_condition=stop_condition,
        session_timeline_classification=session_timeline.classification,
        timeline_upgrade_provenance=session_timeline.upgrade_provenance,
    )
    semantic = manifest.to_semantic_dict()
    semantic["semantic_fingerprint"] = manifest.fingerprint
    write_capture_manifest(output_directory, semantic)
    print(
        f"Capture session written to {output_directory}; {len(loop.retained)} frames retained; "
        f"stop_condition={stop_condition}; scene_id={args.scene_id}; capture_purpose={args.capture_purpose}."
    )
    return 0


def run_capture(argv: list[str] | None = None) -> int:
    import asyncio
    args = _capture_parser().parse_args(argv)
    try:
        return asyncio.run(_run_capture(args))
    except (TemporalCaptureError, CameraNodeClientError) as error:
        print(f"Temporal capture rejected: {error}", file=sys.stderr)
        return _ERROR_EXIT_CODES.get(str(error), 2)


def main_capture() -> None:
    raise SystemExit(run_capture())


def main_mark() -> None:
    raise SystemExit(run_mark())
