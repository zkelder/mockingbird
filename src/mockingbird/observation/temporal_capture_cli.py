"""Command entry points for the Stage 6.6 bounded reviewed temporal capture
against a paired Camera Node.

python -m mockingbird temporal-capture \\
  --camera-node-config <ignored-config.json> \\
  --provider frame-driven-onnx-cuda --provider-config <ignored-model-config.json> \\
  --output <ignored-output-directory> --duration <bounded-seconds>

python -m mockingbird temporal-capture-mark \\
  --capture <capture-directory> --kind wildlife_visible_now [--note "..."]

`temporal-capture` opens exactly one authenticated Camera Node connection,
retains only bounded-trigger frames, and writes an ignored, local capture
directory (frames + `capture-session-manifest.json`). It creates no product
record. See docs/temporal-review-capture-contract.md.
"""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
import sys
from uuid import uuid4

from mockingbird.observation.camera_node_live import (
    CameraNodeAnalysisSource,
    CameraNodeHttpTransport,
    LiveCameraNodeShadowSession,
)
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
    STOP_ACTIVE_TRACK_LIMIT,
    STOP_BYTE_LIMIT,
    STOP_DURATION_ELAPSED,
    STOP_FRAME_LIMIT,
    STOP_HIGH_RESOLUTION_LIMIT,
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
    classify_detection_triggers,
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
# Camera Node: every fresh connection is itself a discontinuity boundary
# (its sequence header restarts, forcing a source rebuild + provider
# generation restart in `_CaptureLoop.run()` below) that clears pretrigger
# context and blocks motion-proposal generation across the gap. A larger
# batch means fewer connections per bounded capture and more continuous
# temporal coverage, at the cost of coarser bound-checking granularity
# between batches, AND slower operator-marker rescue: `_refresh_markers`
# can only discover a marker at a batch boundary, so a batch's worth of
# frames is roughly the worst-case rescue-buffer depth needed (see
# `CaptureBounds.adjacent_context_frame_count`, max 16). 12 keeps one
# batch comfortably within that ceiling with headroom, while still being
# meaningfully less choppy than one-frame-at-a-time polling (12 frames at
# a 2 fps nominal source is ~6 real seconds between checkpoints).
MAX_CONSECUTIVE_RECONNECTS = 5
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
        "--validation-burst", action="store_true",
        help="Explicitly request one labeled engineering high-resolution burst at session start to validate the "
             "burst endpoint end-to-end, independent of any real detector/tracker trigger. Never represents wildlife.",
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
                 shadow_operating_point: float, review_floor: float, privacy_regions: tuple[tuple[float, float, float, float], ...]) -> None:
        self.session = session
        self.output_directory = output_directory
        self.bounds = bounds
        self.shadow_operating_point = shadow_operating_point
        self.review_floor = review_floor
        self.privacy_regions = privacy_regions
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
        for frame, detection_boxes, track_generation_ids, proposal_boxes in list(self.recent_frames):
            if frame.received_at is None:
                continue
            near = markers_near(markers, host_time_iso=frame.received_at.isoformat(), default_lookback_seconds=20)
            if not near:
                continue
            self._retain(
                frame, [TRIGGER_OPERATOR_MARKER], detection_boxes, track_generation_ids, proposal_boxes,
                marker_ids=tuple(item.marker_id for item in near),
            )
            self.post_trigger_remaining = self.bounds.post_trigger_frame_count

    async def run(self, *, started_wall: datetime, duration_seconds: int) -> str:
        consecutive_reconnects = 0
        while True:
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
            except CameraNodeClientError:
                return STOP_TRANSPORT_ERROR
            except ValueError as error:
                # Each `session.run()` batch opens its own bounded transport
                # connection (see CameraNodeHttpTransport.iter_analysis_frames).
                # Confirmed against the real Camera Node: its per-connection
                # `x-mockingbird-sequence` header restarts at 1 on *every*
                # fresh connection while `x-mockingbird-provider-generation`
                # stays unchanged (it tracks the physical camera process, not
                # the HTTP connection) -- so this is not a rare instability
                # case, it is the expected transition at every single batch
                # boundary. `self.session.source` is one long-lived object
                # reused across batches; it still remembers the previous
                # connection's last (higher) sequence number, so the new
                # connection's first frame ("sequence resets to 1") always
                # trips CameraNodeAnalysisSource's own single-connection
                # monotonic-sequence contract on the first `session.run()`
                # call after a successful batch. That source -- correctly,
                # for its own contract -- raises "analysis_frame_sequence"
                # rather than silently accepting a non-increasing sequence
                # within one generation.
                #
                # A fresh source (same bounds/exclusions, cleared
                # sequence/generation state) treats the next batch as a new,
                # valid start. But the source also re-zeroes its
                # source_offset_ms against the new connection's first frame,
                # and the provider's own live tracker still expects offsets
                # to keep increasing from the old connection's zero point --
                # so the very next frame then reads as going backwards in
                # time and the tracker raises ReplayValidationError
                # ("non_monotonic_tracking_frame", a ValueError subclass).
                # Restarting the provider's live generation alongside the
                # fresh source clears that stale tracker state too, exactly
                # as a genuine provider_generation change would.
                recoverable = str(error) in {"analysis_frame_sequence", "non_monotonic_tracking_frame"}
                if not recoverable or consecutive_reconnects >= MAX_CONSECUTIVE_RECONNECTS:
                    return STOP_TRANSPORT_ERROR
                consecutive_reconnects += 1
                self.session.source = CameraNodeAnalysisSource(
                    self.session.source.stream_id, maximum_queue_frames=self.session.source.maximum_queue_frames,
                    maximum_frame_bytes=self.session.source.maximum_frame_bytes,
                    maximum_frame_age_ms=self.session.source.maximum_frame_age_ms,
                    analysis_excluded_regions=self.session.source.analysis_excluded_regions,
                )
                self.session.provider.restart_live_generation(
                    self.session.source.stream_id, "capture_transport_reconnect"
                )
                # A reconnect breaks frame-to-frame adjacency exactly like a
                # real generation change does (the same clearing as the
                # `discontinuity` branch in `_process_result`), even though
                # the Node's own `provider_generation` label is unchanged --
                # the gap during reconnect means the next frame is not a
                # valid predecessor/successor pair for motion-proposal
                # diffing, and stale pretrigger context would span the gap.
                self.generation_reset_count += 1
                self.pretrigger.clear()
                self.plane_cache.clear()
                self.plane_order.clear()
                self.last_frame_id = None
                continue
            consecutive_reconnects = 0
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
        for context_frame, context_triggers in pretrigger_flush:
            self._retain(context_frame, list(context_triggers) + [TRIGGER_PRETRIGGER_CONTEXT], (), (), ())
        if retained_now:
            self._retain(
                frame, triggers, detection_boxes, track_generation_ids,
                proposal_boxes, marker_ids=marker_ids,
                high_resolution=TRIGGER_HIGH_RESOLUTION_BURST in triggers, privacy_interaction=privacy_interaction,
            )
        else:
            self.pretrigger.append((frame, tuple(triggers)))
            # No trigger fired for this frame yet -- but an operator marker
            # written moments from now, correlating backward to right about
            # this frame's own received_at, would only ever be discovered
            # at the *next* batch boundary (see `_refresh_markers`), by
            # which point new frames are already in the future relative to
            # that marker. Keep it rescue-eligible until it ages out.
            self.recent_frames.append((frame, detection_boxes, track_generation_ids, proposal_boxes))

        if frame.frame_id is not None:
            self.last_frame_id = frame.frame_id
            self.last_source_offset_ms = frame.source_offset_ms

    def _retain(self, frame, triggers, detection_boxes, track_generation_ids, proposal_boxes, *, marker_ids=(), high_resolution=False, privacy_interaction=False) -> None:
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
        )
        self.retained.append(record)


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
    trigger, exactly like any other burst capture."""

    from mockingbird.observation.media_contracts import EvidenceBurstRequest
    from hashlib import sha256 as _sha256

    request_id = "validation-burst:" + _sha256(f"{node_session_id_for(session)}:{started_wall.isoformat()}".encode()).hexdigest()[:24]
    request = EvidenceBurstRequest(
        request_id=request_id, stream_id=connection.stream_id, node_session_id="validation-burst-session",
        track_generation_id="validation-burst", trigger_frame_id="validation-burst-trigger",
        trigger_captured_at=started_wall, requested_frame_count=1, requested_profile_id=connection.evidence_profile_id,
        cadence_ms=0, subject_geometry=None, zone_id=None, deadline_at=started_wall + timedelta(seconds=15),
    )
    result = session.transport.request_evidence_burst(request)
    print(f"Validation burst request {request_id}: status={result.status} failure_code={result.failure_code}")
    if result.status != "captured" or not result.frames:
        return
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
    ))


def node_session_id_for(session: LiveCameraNodeShadowSession) -> str:
    return getattr(session.source, "stream_id", "unknown")


async def _run_capture(args: argparse.Namespace) -> int:
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
    )
    started_wall = datetime.now(UTC)
    node_session_id = f"temporal-capture:{uuid4().hex[:16]}"
    try:
        session.start()
        if args.validation_burst:
            _request_validation_burst(session, loop, connection, started_wall=started_wall)
        stop_condition = await loop.run(started_wall=started_wall, duration_seconds=args.duration)
    finally:
        session.stop()
        provider.close()
    ended_wall = datetime.now(UTC)

    config = CaptureSessionConfig(
        schema_version=1, capture_version="temporal-capture-session-v1", stream_id=connection.stream_id,
        transport_key="camera-node-http-multipart-jpeg", provider_key=provider.provider_id,
        analysis_width=loop.analysis_width, analysis_height=loop.analysis_height, nominal_fps=configuration.settings.source_nominal_fps,
        review_score_threshold=args.review_score_threshold, shadow_operating_point=args.shadow_operating_point,
        review_floor=args.review_floor, evidence_profile_id=connection.evidence_profile_id, bounds=bounds,
        privacy_ignore_regions=privacy_regions,
    )
    manifest = CaptureSessionManifest(
        config=config, session_id=f"temporal-capture-{started_wall.strftime('%Y%m%dT%H%M%SZ')}",
        node_session_id=node_session_id, start_host_time_iso=started_wall.isoformat(), end_host_time_iso=ended_wall.isoformat(),
        start_source_offset_ms=loop.retained[0].source_offset_ms if loop.retained else 0,
        end_source_offset_ms=loop.retained[-1].source_offset_ms if loop.retained else 0,
        first_sequence=loop.retained[0].sequence if loop.retained else 0, last_sequence=loop.retained[-1].sequence if loop.retained else 0,
        sequence_gap_count=source.status().sequence_gaps, dropped_frame_count=source.status().dropped_frames,
        coalesced_frame_count=source.status().coalesced_frames, stale_frame_count=source.status().stale_frames,
        generation_reset_count=loop.generation_reset_count, provider_generations=tuple(loop.provider_generations),
        model_fingerprint=bundle.fingerprint,
        tracker_proposal_config_fingerprint=_tracker_proposal_config_fingerprint(configuration),
        frames=tuple(loop.retained), operator_markers=tuple(loop.markers_seen.values()), stop_condition=stop_condition,
    )
    semantic = manifest.to_semantic_dict()
    semantic["semantic_fingerprint"] = manifest.fingerprint
    write_capture_manifest(output_directory, semantic)
    print(f"Capture session written to {output_directory}; {len(loop.retained)} frames retained; stop_condition={stop_condition}.")
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
