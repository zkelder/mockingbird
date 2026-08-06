"""Replay-first continuous detector/tracker provider with shadow-only output."""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime, timedelta
from importlib import import_module
from io import BytesIO
from pathlib import Path
from time import perf_counter
from typing import Any, Protocol

from mockingbird.observation.contracts import (
    DetectionObservation,
    EvidenceCandidate,
    FramePacket,
    ObservationProviderCapabilities,
    ObservationProviderDescriptor,
    ObservationProviderHealth,
    ObservationResult,
    TrackUpdate,
    VisitProposal,
)
from mockingbird.observation.frame_tracker import (
    TRACKER_VERSION,
    ProviderNeutralFrameTracker,
    TerminalTrack,
    TrackView,
    TrackerConfiguration,
    TrackerSupportResolver,
)
from mockingbird.observation.reconnect_continuity import (
    CONTINUE_ACROSS_TRANSPORT_RECONNECT,
    RESET_SOURCE_GENERATION,
    ReconnectBridgeConfig,
    classify_frame_reconnect_boundary,
    is_reconnect_boundary_signal,
)
from mockingbird.observation.replay import ReplayValidationError, semantic_fingerprint


FRAME_DRIVEN_PROVIDER_VERSION = "frame-driven-onnx-cuda-shadow-v1"
FRAME_DRIVEN_CONFIG_VERSION = 1
MAX_EVIDENCE_RING_SIZE = 32
MAX_PRETRIGGER_FRAMES = 8


class FrameDetector(Protocol):
    def probe(self) -> dict[str, object]: ...
    def load(self) -> None: ...
    async def infer_frame(self, frame: FramePacket) -> tuple[DetectionObservation, ...]: ...
    def finalize_replay(self) -> None: ...
    def close(self) -> None: ...
    def report_metadata(self) -> dict[str, object]: ...
    def execution_facts(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class FrameDrivenSettings:
    source_nominal_fps: float = 5.0
    baseline_detector_fps: float = 1.0
    candidate_detector_fps: float = 4.0
    maximum_pending_detector_frames: int = 1
    strong_detection_threshold: float = 0.70
    minimum_detector_confirmations: int = 2
    minimum_tracker_support_frames: int = 1
    maximum_missed_frames: int = 3
    maximum_frame_gap_ms: int = 1500
    tracker_expiry_ms: int = 1200
    maximum_track_duration_ms: int = 30000
    maximum_active_tracks: int = 24
    evidence_ring_size: int = 8
    pretrigger_frame_count: int = 2
    minimum_iou: float = 0.05
    maximum_centroid_distance: float = 0.22
    ambiguity_margin: float = 0.01
    maximum_unsupported_detector_ms: int = 5000
    negative_detector_frames_to_end: int = 2
    ambiguous_reentry_window_ms: int = 1500

    def __post_init__(self) -> None:
        if (
            self.source_nominal_fps <= 0
            or self.baseline_detector_fps <= 0
            or self.candidate_detector_fps < self.baseline_detector_fps
            or self.candidate_detector_fps > self.source_nominal_fps
            or self.maximum_pending_detector_frames != 1
            or not 1 <= self.evidence_ring_size <= MAX_EVIDENCE_RING_SIZE
            or not 0 <= self.pretrigger_frame_count <= MAX_PRETRIGGER_FRAMES
            or self.maximum_unsupported_detector_ms < 1
            or self.negative_detector_frames_to_end < 1
            or self.ambiguous_reentry_window_ms < 1
        ):
            raise ValueError("invalid_frame_driven_settings")

    def tracker_configuration(self) -> TrackerConfiguration:
        return TrackerConfiguration(
            strong_detection_threshold=self.strong_detection_threshold,
            minimum_detector_confirmations=self.minimum_detector_confirmations,
            minimum_tracker_support_frames=self.minimum_tracker_support_frames,
            maximum_missed_frames=self.maximum_missed_frames,
            maximum_frame_gap_ms=self.maximum_frame_gap_ms,
            tracker_expiry_ms=self.tracker_expiry_ms,
            maximum_track_duration_ms=self.maximum_track_duration_ms,
            maximum_active_tracks=self.maximum_active_tracks,
            minimum_iou=self.minimum_iou,
            maximum_centroid_distance=self.maximum_centroid_distance,
            ambiguity_margin=self.ambiguity_margin,
            maximum_unsupported_detector_ms=self.maximum_unsupported_detector_ms,
            negative_detector_frames_to_end=self.negative_detector_frames_to_end,
            ambiguous_reentry_window_ms=self.ambiguous_reentry_window_ms,
        )


@dataclass(frozen=True)
class FrameDrivenProviderConfiguration:
    settings: FrameDrivenSettings
    model_bundle_path: Path

    @classmethod
    def load(cls, path: Path) -> "FrameDrivenProviderConfiguration":
        import json

        if path.is_symlink() or not path.is_file():
            raise ReplayValidationError("invalid_frame_driven_configuration")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ReplayValidationError("invalid_frame_driven_configuration") from error
        if not isinstance(payload, dict) or payload.get("schema_version") != FRAME_DRIVEN_CONFIG_VERSION:
            raise ReplayValidationError("invalid_frame_driven_configuration")
        relative = payload.get("model_bundle")
        values = payload.get("settings", {})
        if (
            not isinstance(relative, str)
            or not relative
            or Path(relative).is_absolute()
            or ".." in Path(relative).parts
            or not isinstance(values, dict)
        ):
            raise ReplayValidationError("invalid_frame_driven_configuration")
        root = path.parent.resolve(strict=True)
        bundle = (path.parent / relative)
        if bundle.is_symlink() or not bundle.is_file():
            raise ReplayValidationError("invalid_frame_driven_configuration")
        bundle = bundle.resolve(strict=True)
        if not bundle.is_relative_to(root):
            raise ReplayValidationError("invalid_frame_driven_configuration")
        try:
            settings = FrameDrivenSettings(**values)
        except (TypeError, ValueError) as error:
            raise ReplayValidationError("invalid_frame_driven_configuration") from error
        return cls(settings, bundle)


class _PortablePatchSupport:
    """Small deterministic patch matcher; model/library types never leave this adapter."""

    def __init__(self) -> None:
        self._templates: dict[str, Any] = {}

    def remember(self, frame: FramePacket, track: TrackView) -> None:
        patch = self._patch(frame, track.bounding_box)
        if patch is not None:
            self._templates[track.generation_id] = patch

    def forget(self, generation_id: str) -> None:
        self._templates.pop(generation_id, None)

    def clear(self) -> None:
        self._templates.clear()

    def __call__(self, frame: FramePacket, track: TrackView) -> tuple[float, float, float, float] | None:
        template = self._templates.get(track.generation_id)
        if template is None:
            return None
        numpy = import_module("numpy")
        candidates: list[tuple[float, tuple[float, float, float, float]]] = []
        for dx in (-0.04, -0.02, 0.0, 0.02, 0.04):
            for dy in (-0.04, -0.02, 0.0, 0.02, 0.04):
                box = _shift_box(track.bounding_box, dx, dy)
                patch = self._patch(frame, box)
                if patch is None:
                    continue
                difference = float(numpy.mean(numpy.abs(patch - template)))
                candidates.append((difference, box))
        if not candidates:
            return None
        difference, box = min(candidates, key=lambda item: (item[0], item[1]))
        return box if difference <= 0.18 else None

    def _patch(self, frame: FramePacket, box: tuple[float, float, float, float]) -> Any | None:
        if frame.source_path is None and frame.payload is None:
            return None
        try:
            image_module = import_module("PIL.Image")
            numpy = import_module("numpy")
            source_input = BytesIO(frame.payload) if frame.payload is not None else frame.source_path
            with image_module.open(source_input) as source:
                source.load()
                gray = source.convert("L")
                width, height = gray.size
                crop = gray.crop((
                    round(box[0] * width),
                    round(box[1] * height),
                    max(round(box[0] * width) + 1, round(box[2] * width)),
                    max(round(box[1] * height) + 1, round(box[3] * height)),
                )).resize((16, 16), image_module.Resampling.BILINEAR)
                return numpy.asarray(crop, dtype="float32") / 255.0
        except Exception:
            return None


class FrameDrivenObservationProvider:
    provider_id = "frame-driven-onnx-cuda"
    display_name = "Frame-driven ONNX CUDA Shadow Provider"
    capabilities = ObservationProviderCapabilities(
        False,
        True,
        True,
        True,
        True,
        True,
        deterministic_replay=True,
        frame_driven=True,
        cuda_detector=True,
        tracking=True,
        shadow_visit_proposals=True,
        production_proposal_authority=False,
        continuous_live_stream_input=True,
        camera_node_analysis_stream=True,
        rolling_live_encoded_buffer=False,
        high_resolution_burst=True,
        species_interpretation=False,
    )

    def __init__(
        self,
        *,
        detector: FrameDetector,
        settings: FrameDrivenSettings | None = None,
        tracker_support: TrackerSupportResolver | None = None,
        reconnect_bridge_config: ReconnectBridgeConfig | None = None,
    ) -> None:
        self.detector = detector
        self.settings = settings or FrameDrivenSettings()
        self.reconnect_bridge_config = reconnect_bridge_config or ReconnectBridgeConfig()
        self._patch_support = _PortablePatchSupport() if tracker_support is None else None
        self._support = tracker_support or self._patch_support
        self._tracker: ProviderNeutralFrameTracker | None = None
        self._stream_id: str | None = None
        self._mode = "replay"
        self._loaded = False
        self._last_detector_offset_ms: int | None = None
        self._pretrigger: deque[FramePacket] = deque(maxlen=max(1, self.settings.pretrigger_frame_count))
        self._evidence: dict[str, dict[str, EvidenceCandidate]] = {}
        self._finalized_generations: set[str] = set()
        self._pending_final_results: list[ObservationResult] = []
        self._tracker_latencies_ms: list[float] = []
        self._facts: dict[str, int] = {}
        self._reset_facts()

    @property
    def active_track_count(self) -> int:
        return self._tracker.active_count if self._tracker is not None else 0

    def load(self) -> None:
        if self._loaded:
            raise ReplayValidationError("provider_already_loaded")
        self.detector.load()
        self._loaded = True

    def close(self) -> None:
        self.reset()
        self.detector.close()
        self._loaded = False

    def reset(self) -> None:
        if self._tracker is not None:
            self._tracker.reset()
        self._tracker = None
        self._stream_id = None
        self._last_detector_offset_ms = None
        self._pretrigger.clear()
        self._evidence.clear()
        self._finalized_generations.clear()
        self._pending_final_results.clear()
        if self._patch_support is not None:
            self._patch_support.clear()

    async def health(self, *, stream_id: str | None = None) -> ObservationProviderHealth:
        probe = self.detector.probe()
        healthy = bool(probe.get("cuda_available") and probe.get("model_bundle_compatible"))
        return ObservationProviderHealth(
            "idle" if healthy else "degraded",
            healthy,
            "Frame-driven CUDA replay is available; production authority remains disabled."
            if healthy
            else "A compatible CUDA detector and model bundle are required.",
        )

    async def describe(self, *, stream_id: str | None = None) -> ObservationProviderDescriptor:
        return ObservationProviderDescriptor(
            self.provider_id,
            self.display_name,
            self.capabilities,
            await self.health(stream_id=stream_id),
        )

    async def replay_frames(self, frames: tuple[FramePacket, ...]) -> tuple[ObservationResult, ...]:
        if not self._loaded:
            raise ReplayValidationError("provider_not_loaded")
        self.reset()
        self._reset_facts()
        self._mode = "replay"
        if not frames:
            self.detector.finalize_replay()
            return ()
        self._stream_id = frames[0].stream_id
        self._tracker = ProviderNeutralFrameTracker(
            self._stream_id,
            self.settings.tracker_configuration(),
            support_resolver=self._support,
            reconnect_bridge_config=self.reconnect_bridge_config,
        )
        results: list[ObservationResult] = []
        previous_frame: FramePacket | None = None
        for frame in frames:
            # A replay input built without `captured_at_iso` (every legacy,
            # non-Stage-6.8 export) never sets `captured_at` at all;
            # `_process_frame` already tolerates that with a deterministic
            # fallback derived from `source_offset_ms`. Applying the same
            # fallback here, before it, keeps `note_reconnect_boundary`
            # (which needs a real timestamp) and `_process_frame` looking at
            # one consistent frame -- calling it twice is a no-op once
            # `captured_at` is set.
            frame = _with_fallback_captured_at(frame)
            boundary_updates: tuple[TrackUpdate, ...] = ()
            if previous_frame is not None and is_reconnect_boundary_signal(previous_frame, frame):
                # Stage 6.11: a discontinuity signal fired (see
                # docs/session-timeline-contract.md for how a reconnect-safe
                # replay input sets it), but that signal alone no longer
                # forces a reset -- `classify_frame_reconnect_boundary`
                # distinguishes a benign transport reconnect (bridged) from
                # a genuine source discontinuity (reset). See
                # docs/reconnect-continuity-contract.md for the full
                # decision contract.
                decision = classify_frame_reconnect_boundary(previous_frame, frame, self.reconnect_bridge_config)
                self._facts["reconnect_boundaries"] += 1
                if decision.decision == CONTINUE_ACROSS_TRANSPORT_RECONNECT:
                    self._facts["reconnect_bridges_attempted"] += 1
                    assert self._tracker is not None and frame.captured_at is not None
                    step = self._tracker.note_reconnect_boundary(
                        boundary_offset_ms=frame.source_offset_ms or 0, captured_at=frame.captured_at,
                    )
                    boundary_updates = step.updates
                else:
                    # Both remaining decisions reset tracking, distinguished
                    # only by *why*, for honest reporting: a confidently
                    # evidenced source-generation change reuses the existing
                    # "provider_reset" reason `restart_live_generation`
                    # already establishes; insufficient bridge provenance
                    # gets its own distinct reason rather than being
                    # conflated with a known generation change. Unlike the
                    # live path, the drained results are kept -- replay has
                    # no other place to report a generation that ended
                    # exactly at this boundary.
                    if decision.decision == RESET_SOURCE_GENERATION:
                        self._facts["resets_true_source_change"] += 1
                        reset_reason = "provider_reset"
                    else:
                        self._facts["resets_insufficient_provenance"] += 1
                        reset_reason = "insufficient_reconnect_provenance"
                    results.extend(self._reset_tracking_for_replay_discontinuity(reset_reason))
            results.append(await self._process_frame(frame, extra_updates=boundary_updates))
            previous_frame = frame
        self.finalize_replay()
        results.extend(self.drain_final_results())
        return tuple(results)

    def _reset_tracking_for_replay_discontinuity(self, reason: str) -> tuple[ObservationResult, ...]:
        """Finalize the current tracker generation and start a fresh one
        mid-replay, mirroring `restart_live_generation`'s reset shape
        without touching that live-only method (kept independent so this
        addition carries zero risk to the already-tested live reconnect
        path)."""

        self._finalize_tracking(reason)
        drained = self.drain_final_results()
        self._last_detector_offset_ms = None
        self._pretrigger.clear()
        self._evidence.clear()
        if self._patch_support is not None:
            self._patch_support.clear()
        self._tracker = ProviderNeutralFrameTracker(
            self._stream_id, self.settings.tracker_configuration(),
            support_resolver=self._support, reconnect_bridge_config=self.reconnect_bridge_config,
        )
        return drained

    def start_live(self, stream_id: str) -> None:
        """Start one bounded transient live-shadow generation."""
        if not self._loaded:
            raise ReplayValidationError("provider_not_loaded")
        if not stream_id:
            raise ReplayValidationError("frame_tracking_metadata_required")
        self.reset()
        self._reset_facts()
        self._mode = "live_shadow"
        self._stream_id = stream_id
        self._tracker = ProviderNeutralFrameTracker(
            stream_id,
            self.settings.tracker_configuration(),
            support_resolver=self._support,
            reconnect_bridge_config=self.reconnect_bridge_config,
        )

    async def observe_live_frame(self, frame: FramePacket) -> ObservationResult:
        if self._mode != "live_shadow" or self._stream_id != frame.stream_id:
            raise ReplayValidationError("live_stream_not_started")
        return await self._process_frame(frame)

    def restart_live_generation(self, stream_id: str, reason: str = "provider_reset") -> None:
        """Replace transient track state while retaining one loaded detector session."""
        if self._mode != "live_shadow":
            raise ReplayValidationError("live_stream_not_started")
        self._finalize_tracking(reason)
        self.drain_final_results()
        self.reset()
        self._mode = "live_shadow"
        self._stream_id = stream_id
        self._tracker = ProviderNeutralFrameTracker(
            stream_id,
            self.settings.tracker_configuration(),
            support_resolver=self._support,
            reconnect_bridge_config=self.reconnect_bridge_config,
        )

    def stop_live(self, reason: str = "provider_reset") -> tuple[ObservationResult, ...]:
        """Finalize and clear transient live state without durable side effects."""
        if self._mode != "live_shadow":
            return ()
        self._finalize_tracking(reason)
        results = self.drain_final_results()
        try:
            self.detector.finalize_replay()
        finally:
            self.reset()
        return results

    async def _process_frame(
        self, frame: FramePacket, *, extra_updates: tuple[TrackUpdate, ...] = (),
    ) -> ObservationResult:
        if self._tracker is None or self._stream_id is None:
            raise ReplayValidationError("provider_not_loaded")
        frame = _with_fallback_captured_at(frame)
        self._facts["frames_supplied"] += 1
        detector_ran = self._should_infer(frame)
        detections: tuple[DetectionObservation, ...] = ()
        if detector_ran:
            raw = await self.detector.infer_frame(frame)
            self._last_detector_offset_ms = frame.source_offset_ms
            self._facts["frames_inferred"] += 1
            detections = tuple(
                replace(item, provider_id=self.provider_id)
                for item in raw
                if not _excluded(item.bounding_box, frame.analysis_excluded_regions)
            )
            self._facts["detector_observations"] += len(detections)
            if any(item.is_animal is True for item in detections):
                self._facts["animal_positive_inference_frames"] += 1
        started = perf_counter()
        try:
            step = self._tracker.observe(frame, detections, detector_ran=detector_ran)
        except ValueError as error:
            raise ReplayValidationError(str(error)) from error
        self._tracker_latencies_ms.append((perf_counter() - started) * 1000)
        # `extra_updates` carries the "temporarily lost, pending
        # reacquisition" transition `note_reconnect_boundary` produced for
        # this exact frame's boundary (Stage 6.11), folded into this same
        # frame's result rather than a separate phantom `ObservationResult`
        # -- preserving "one `ObservationResult` per supplied frame" exactly
        # as before this stage.
        all_updates = extra_updates + step.updates
        self._facts["tracker_updates"] += len(all_updates)
        self._facts["ambiguous_associations"] += step.ambiguous_associations
        self._facts["ambiguous_reentries"] += step.ambiguous_reentries
        self._facts["reconnect_bridges_continued"] += step.reconnect_bridges_continued
        self._facts["reconnect_bridges_expired"] += step.reconnect_bridges_expired
        self._facts["reconnect_ambiguous_associations"] += step.reconnect_ambiguous_associations
        terminal_evidence: list[EvidenceCandidate] = []
        proposals: list[VisitProposal] = []
        for update in all_updates:
            if update.status == "started":
                self._facts["tracks_started"] += 1
                self._seed_evidence(frame, update)
            else:
                self._update_evidence(frame, update, bool(detections))
            if update.lifecycle_state == "confirmed":
                self._facts["confirmed_update_count"] += 1
            if self._patch_support is not None and update.bounding_box is not None and update.lifecycle_state != "temporarily_lost":
                self._patch_support.remember(frame, _view_from_update(update))
        for terminal in step.terminals:
            evidence, proposal = self._finalize_terminal(terminal)
            terminal_evidence.extend(evidence)
            if proposal is not None:
                proposals.append(proposal)
        self._pretrigger.append(frame)
        return ObservationResult(
            self.provider_id,
            self._mode,
            frame.stream_id,
            frame.captured_at,
            frame_packets=(frame,),
            detection_observations=detections,
            track_updates=all_updates,
            evidence_candidates=tuple(terminal_evidence),
            visit_proposals=tuple(proposals),
        )

    def finalize_replay(self) -> None:
        self._finalize_tracking("end_of_replay")
        self.detector.finalize_replay()

    def _finalize_tracking(self, reason: str) -> None:
        if self._tracker is None or self._stream_id is None:
            return
        step = self._tracker.finalize(reason)
        evidence: list[EvidenceCandidate] = []
        proposals: list[VisitProposal] = []
        for terminal in step.terminals:
            items, proposal = self._finalize_terminal(terminal)
            evidence.extend(items)
            if proposal is not None:
                proposals.append(proposal)
        if step.updates or evidence or proposals:
            observed_at = step.updates[-1].captured_at if step.updates else None
            self._pending_final_results.append(ObservationResult(
                self.provider_id,
                self._mode,
                self._stream_id,
                observed_at,
                track_updates=step.updates,
                evidence_candidates=tuple(evidence),
                visit_proposals=tuple(proposals),
            ))

    def drain_final_results(self) -> tuple[ObservationResult, ...]:
        values = tuple(self._pending_final_results)
        self._pending_final_results.clear()
        return values

    def report_metadata(self) -> dict[str, object]:
        detector = self.detector.report_metadata()
        return {
            "provider_key": self.provider_id,
            "provider_version": FRAME_DRIVEN_PROVIDER_VERSION,
            "settings": asdict(self.settings),
            "tracker": {"version": TRACKER_VERSION, "configuration": asdict(self.settings.tracker_configuration())},
            "reconnect_bridge": asdict(self.reconnect_bridge_config),
            "detector": detector.get("model"),
            "shadow_mode": True,
            "production_proposal_authority": False,
            "limitations": [
                "live input is shadow-only and uses bounded latest-frame coalescing",
                "portable spatial patch tracking is bounded and not species interpretation",
                "no production proposal authority, species interpretation, or product writes",
            ],
        }

    def replay_semantic_facts(self) -> dict[str, int]:
        return dict(sorted(self._facts.items()))

    def execution_facts(self) -> dict[str, object]:
        detector = self.detector.execution_facts()
        tracker_values = sorted(self._tracker_latencies_ms)
        return {
            **detector,
            "tracker_processing_count": len(tracker_values),
            "tracker_processing_ms_median": _median(tracker_values),
        }

    def _should_infer(self, frame: FramePacket) -> bool:
        if frame.source_offset_ms is None:
            raise ReplayValidationError("frame_tracking_metadata_required")
        if self._last_detector_offset_ms is None:
            return True
        fps = self.settings.candidate_detector_fps if self.active_track_count else self.settings.baseline_detector_fps
        interval_ms = 1000.0 / fps
        return frame.source_offset_ms - self._last_detector_offset_ms + 1e-9 >= interval_ms

    def _seed_evidence(self, frame: FramePacket, update: TrackUpdate) -> None:
        selected: dict[str, EvidenceCandidate] = {}
        if self.settings.pretrigger_frame_count:
            prior = list(self._pretrigger)[-self.settings.pretrigger_frame_count :]
            if prior:
                selected["pretrigger"] = self._candidate(prior[-1], update, "pretrigger")
        selected["detector_confirmed"] = self._candidate(frame, update, "detector_confirmed")
        selected["tracked_best"] = self._candidate(frame, update, "tracked_best")
        self._evidence[update.generation_id] = selected

    def _update_evidence(self, frame: FramePacket, update: TrackUpdate, detector_ran: bool) -> None:
        selected = self._evidence.get(update.generation_id)
        if selected is None or update.bounding_box is None or update.lifecycle_state == "temporarily_lost":
            return
        candidate = self._candidate(frame, update, "tracked_best")
        existing = selected.get("tracked_best")
        if existing is None or _quality(candidate) > _quality(existing):
            selected["tracked_best"] = candidate
        if detector_ran:
            selected.setdefault("alternative", self._candidate(frame, update, "alternative"))
        selected["final_supported"] = self._candidate(frame, update, "final_supported")

    def _candidate(self, frame: FramePacket, update: TrackUpdate, role: str) -> EvidenceCandidate:
        box = update.bounding_box
        area = 0.0 if box is None else (box[2] - box[0]) * (box[3] - box[1])
        return EvidenceCandidate(
            frame.media_asset_id,
            frame.stream_id,
            role,
            frame.captured_at,
            frame.frame_id,
            frame.source_offset_ms,
            frame.width,
            frame.height,
            box,
            update.generation_id,
            update.detector_provenance,
            TRACKER_VERSION,
            (
                ("subject_area", round(area, 8)),
                ("detector_confidence", update.confidence),
                ("track_supported", True),
                ("detector_support", update.detector_confirmation_count),
                ("tracker_support", update.tracker_support_count),
                ("supporting_frame_count", len(update.supporting_frame_ids)),
                ("temporal_alignment", "uncertain" if role == "pretrigger" else "aligned"),
                ("track_active_at_capture", role != "pretrigger"),
            ),
            True,
            True,
        )

    def _finalize_terminal(self, terminal: TerminalTrack) -> tuple[tuple[EvidenceCandidate, ...], VisitProposal | None]:
        generation = terminal.view.generation_id
        if generation in self._finalized_generations:
            return (), None
        self._finalized_generations.add(generation)
        selected = self._evidence.pop(generation, {})
        if self._patch_support is not None:
            self._patch_support.forget(generation)
        ordered = tuple(
            selected[role]
            for role in ("pretrigger", "detector_confirmed", "tracked_best", "final_supported", "alternative")
            if role in selected
        )[: self.settings.evidence_ring_size]
        if not terminal.confirmed:
            self._facts["tracks_rejected_or_lost"] += 1
            return ordered, None
        self._facts["tracks_confirmed"] += 1
        self._facts["shadow_proposals"] += 1
        self._facts["evidence_candidates"] += len(ordered)
        view = terminal.view
        proposal_key = "frame-driven:" + semantic_fingerprint((
            FRAME_DRIVEN_PROVIDER_VERSION,
            view.generation_id,
            view.first_offset_ms,
            view.last_offset_ms,
        ))
        evidence_ids = tuple(dict.fromkeys(item.media_asset_id for item in ordered))
        proposal = VisitProposal(
            proposal_key,
            self._mode,
            self._stream_id or "",
            evidence_ids,
            "confirmed_visit",
            view.first_offset_ms,
            view.last_offset_ms,
            None,
            True,
            proposal_key,
            view.broad_class,
            view.generation_id,
            "onnx-cuda",
            TRACKER_VERSION,
            view.supporting_frame_ids,
            terminal.terminal_reason,
            self.provider_id,
            FRAME_DRIVEN_PROVIDER_VERSION,
        )
        return ordered, proposal

    def _reset_facts(self) -> None:
        self._facts = {
            "frames_supplied": 0,
            "frames_inferred": 0,
            "animal_positive_inference_frames": 0,
            "detector_observations": 0,
            "tracker_updates": 0,
            "tracks_started": 0,
            "tracks_confirmed": 0,
            "tracks_rejected_or_lost": 0,
            "confirmed_update_count": 0,
            "ambiguous_associations": 0,
            "ambiguous_reentries": 0,
            "shadow_proposals": 0,
            "evidence_candidates": 0,
            # Stage 6.11 reconnect-continuity counters -- see
            # docs/reconnect-continuity-contract.md and
            # `replay._reconnect_metrics` for how these surface in a replay
            # report. `reconnect_boundaries` is every recognized
            # discontinuity signal; the four decision outcomes below always
            # sum to it (`reconnect_bridges_attempted` +
            # `resets_true_source_change` + `resets_insufficient_provenance`
            # == `reconnect_boundaries`), and every attempted bridge itself
            # resolves to exactly one of `reconnect_bridges_continued`
            # (this specific track reacquired) or `_expired` (bridge window
            # closed first) per pending track.
            "reconnect_boundaries": 0,
            "reconnect_bridges_attempted": 0,
            "reconnect_bridges_continued": 0,
            "reconnect_bridges_expired": 0,
            "reconnect_ambiguous_associations": 0,
            "resets_true_source_change": 0,
            "resets_insufficient_provenance": 0,
        }


def _view_from_update(update: TrackUpdate) -> TrackView:
    assert update.bounding_box is not None
    return TrackView(
        update.track_id,
        update.generation_id,
        update.lifecycle_state if update.lifecycle_state in {"tentative", "confirmed", "temporarily_lost"} else "tentative",
        update.broad_class or "animal",
        update.bounding_box,
        update.source_offset_ms or 0,
        update.source_offset_ms or 0,
        update.detector_confirmation_count,
        update.tracker_support_count,
        update.confidence,
        update.supporting_frame_ids,
    )


def _with_fallback_captured_at(frame: FramePacket) -> FramePacket:
    """A replay input built without `captured_at_iso` (every legacy,
    non-Stage-6.8 export -- see `ReplayFrame`) never sets `captured_at` at
    all. Both ordinary per-frame processing and the Stage 6.11 reconnect-
    boundary decision need a real timestamp; this deterministic fallback
    (derived only from the frame's own `source_offset_ms`, never a
    recomputed current-wall-clock value) is a no-op once `captured_at` is
    already set."""
    if frame.captured_at is None and frame.source_offset_ms is not None:
        return replace(
            frame, captured_at=datetime(1970, 1, 1, tzinfo=UTC) + timedelta(milliseconds=frame.source_offset_ms),
        )
    return frame


def _shift_box(box: tuple[float, float, float, float], dx: float, dy: float) -> tuple[float, float, float, float]:
    width, height = box[2] - box[0], box[3] - box[1]
    left = max(0.0, min(1.0 - width, box[0] + dx))
    top = max(0.0, min(1.0 - height, box[1] + dy))
    return (left, top, left + width, top + height)


def _excluded(
    box: tuple[float, float, float, float] | None,
    exclusions: tuple[tuple[float, float, float, float], ...],
) -> bool:
    if box is None:
        return False
    center = ((box[0] + box[2]) / 2.0, (box[1] + box[3]) / 2.0)
    return any(left <= center[0] <= right and top <= center[1] <= bottom for left, top, right, bottom in exclusions)


def _quality(candidate: EvidenceCandidate) -> tuple[float, float, int, str]:
    facts = dict(candidate.quality_facts)
    return (
        float(facts.get("detector_confidence") or 0.0),
        float(facts.get("subject_area") or 0.0),
        -(candidate.source_offset_ms or 0),
        candidate.frame_id or "",
    )


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    middle = len(values) // 2
    if len(values) % 2:
        return round(values[middle], 3)
    return round((values[middle - 1] + values[middle]) / 2.0, 3)
