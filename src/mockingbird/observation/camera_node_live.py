"""Bounded PC-side Camera Node analysis input for live shadow observation."""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from http.client import HTTPConnection, HTTPSConnection
import json
import socket
import threading
from typing import Iterator, Protocol

from mockingbird.observation.contracts import EvidenceCandidate, FramePacket, ObservationResult
from mockingbird.observation.frame_driven_provider import (
    FRAME_DRIVEN_PROVIDER_VERSION,
    FrameDrivenObservationProvider,
)
from mockingbird.observation.media_contracts import (
    AnalysisFrameEnvelope,
    EvidenceBurstFrame,
    EvidenceBurstRequest,
    EvidenceBurstResult,
)
from mockingbird.source_providers.camera_node import (
    CameraNodeClientError,
    UrlLibCameraNodeRequester,
    normalize_camera_node_address,
)


DEFAULT_MAXIMUM_QUEUE_FRAMES = 4
DEFAULT_MAXIMUM_FRAME_BYTES = 2_000_000
DEFAULT_MAXIMUM_FRAME_AGE_MS = 2_000
MAXIMUM_HEALTH_HISTORY = 32


@dataclass(frozen=True)
class AnalysisSourceStatus:
    stream_id: str
    state: str
    queue_depth: int
    queue_capacity: int
    received_frames: int
    delivered_frames: int
    sequence_gaps: int
    dropped_frames: int
    coalesced_frames: int
    stale_frames: int
    generation_resets: int
    current_provider_generation: str | None
    newest_frame_age_ms: int | None
    actual_received_fps: float | None
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class _ReceivedFrame:
    envelope: AnalysisFrameEnvelope
    received_at: datetime


class CameraNodeAnalysisSource:
    """Validate and coalesce an authenticated Node stream without persistence."""

    def __init__(
        self,
        stream_id: str,
        *,
        maximum_queue_frames: int = DEFAULT_MAXIMUM_QUEUE_FRAMES,
        maximum_frame_bytes: int = DEFAULT_MAXIMUM_FRAME_BYTES,
        maximum_frame_age_ms: int = DEFAULT_MAXIMUM_FRAME_AGE_MS,
        analysis_excluded_regions: tuple[tuple[float, float, float, float], ...] = (),
    ) -> None:
        if (
            not stream_id
            or not 1 <= maximum_queue_frames <= 16
            or not 1024 <= maximum_frame_bytes <= 16_000_000
            or not 100 <= maximum_frame_age_ms <= 10_000
            or len(analysis_excluded_regions) > 64
            or any(not _valid_normalized_box(box) for box in analysis_excluded_regions)
        ):
            raise ValueError("invalid_analysis_source_bounds")
        self.stream_id = stream_id
        self.maximum_queue_frames = maximum_queue_frames
        self.maximum_frame_bytes = maximum_frame_bytes
        self.maximum_frame_age_ms = maximum_frame_age_ms
        self.analysis_excluded_regions = analysis_excluded_regions
        self._queue: deque[_ReceivedFrame] = deque()
        self._lock = threading.RLock()
        self._generation: str | None = None
        self._last_sequence: int | None = None
        self._first_monotonic_ns: int | None = None
        self._first_captured_at: datetime | None = None
        self._received_times: deque[datetime] = deque(maxlen=MAXIMUM_HEALTH_HISTORY)
        self._received = 0
        self._delivered = 0
        self._sequence_gaps = 0
        self._dropped = 0
        self._coalesced = 0
        self._stale = 0
        self._generation_resets = 0
        self._stopped = False

    def offer(
        self,
        envelope: AnalysisFrameEnvelope,
        *,
        received_at: datetime | None = None,
    ) -> None:
        with self._lock:
            self._offer(envelope, received_at=received_at)

    def _offer(
        self, envelope: AnalysisFrameEnvelope, *, received_at: datetime | None = None
    ) -> None:
        if self._stopped:
            raise ValueError("analysis_source_stopped")
        if envelope.stream_id != self.stream_id:
            raise ValueError("analysis_frame_stream")
        if len(envelope.payload) > self.maximum_frame_bytes:
            raise ValueError("analysis_frame_too_large")
        if envelope.content_type == "image/jpeg" and not envelope.payload.startswith(b"\xff\xd8"):
            raise ValueError("analysis_frame_content")
        if sha256(envelope.payload).hexdigest() != envelope.content_hash:
            raise ValueError("analysis_frame_hash")
        received = received_at or datetime.now(UTC)
        if received.tzinfo is None:
            raise ValueError("analysis_receive_timestamp")
        if self._generation != envelope.provider_generation:
            if self._generation is not None:
                self._generation_resets += 1
            self._queue.clear()
            self._last_sequence = None
            self._first_monotonic_ns = envelope.source_monotonic_ns
            self._first_captured_at = envelope.captured_at
            self._generation = envelope.provider_generation
        if self._last_sequence is not None:
            if envelope.sequence <= self._last_sequence:
                raise ValueError("analysis_frame_sequence")
            self._sequence_gaps += max(0, envelope.sequence - self._last_sequence - 1)
        self._last_sequence = envelope.sequence
        if len(self._queue) >= self.maximum_queue_frames:
            self._queue.popleft()
            self._dropped += 1
        self._queue.append(_ReceivedFrame(envelope, received))
        self._received += 1
        self._received_times.append(received)

    def pop_latest(self, *, now: datetime | None = None) -> FramePacket | None:
        with self._lock:
            return self._pop_latest(now=now)

    def _pop_latest(self, *, now: datetime | None = None) -> FramePacket | None:
        reference = now or datetime.now(UTC)
        if reference.tzinfo is None:
            raise ValueError("analysis_receive_timestamp")
        while self._queue and self._age_ms(self._queue[0], reference) > self.maximum_frame_age_ms:
            self._queue.popleft()
            self._stale += 1
        if not self._queue:
            return None
        newest = self._queue.pop()
        self._coalesced += len(self._queue)
        self._queue.clear()
        envelope = newest.envelope
        self._delivered += 1
        if envelope.source_monotonic_ns is not None and self._first_monotonic_ns is not None:
            source_offset_ms = max(0, (envelope.source_monotonic_ns - self._first_monotonic_ns) // 1_000_000)
        elif self._first_captured_at is not None:
            source_offset_ms = max(0, int((envelope.captured_at - self._first_captured_at).total_seconds() * 1000))
        else:
            source_offset_ms = 0
        return FramePacket(
            stream_id=envelope.stream_id,
            media_asset_id=f"shadow-frame:{envelope.frame_id}",
            captured_at=envelope.captured_at,
            frame_id=envelope.frame_id,
            source_offset_ms=source_offset_ms,
            width=envelope.width,
            height=envelope.height,
            analysis_excluded_regions=self.analysis_excluded_regions,
            payload=envelope.payload,
            frame_sequence=envelope.sequence,
            node_session_id=envelope.node_session_id,
            source_monotonic_ns=envelope.source_monotonic_ns,
            received_at=newest.received_at,
            provider_generation=envelope.provider_generation,
            timing_facts=envelope.timing_facts + (
                ("pc_received_at", newest.received_at.isoformat()),
                (
                    "node_to_host_clock_offset_ms",
                    round((newest.received_at - envelope.captured_at).total_seconds() * 1000, 3),
                ),
                ("node_to_host_clock_alignment", "uncertain"),
            ),
        )

    def status(self, *, now: datetime | None = None) -> AnalysisSourceStatus:
        with self._lock:
            return self._status(now=now)

    def _status(self, *, now: datetime | None = None) -> AnalysisSourceStatus:
        reference = now or datetime.now(UTC)
        newest = self._queue[-1] if self._queue else None
        age = self._age_ms(newest, reference) if newest is not None else None
        fps = None
        if len(self._received_times) >= 2:
            duration = (self._received_times[-1] - self._received_times[0]).total_seconds()
            if duration > 0:
                fps = round((len(self._received_times) - 1) / duration, 3)
        degraded = bool(self._dropped or self._stale or self._sequence_gaps)
        return AnalysisSourceStatus(
            self.stream_id,
            "stopped" if self._stopped else "degraded" if degraded else "running",
            len(self._queue),
            self.maximum_queue_frames,
            self._received,
            self._delivered,
            self._sequence_gaps,
            self._dropped,
            self._coalesced,
            self._stale,
            self._generation_resets,
            self._generation,
            age,
            fps,
            (
                "latest-frame coalescing is intentional under host backpressure",
                "node-to-host clock alignment remains uncertain without synchronized clocks",
            ),
        )

    def reset(self) -> None:
        with self._lock:
            self._reset()

    def _reset(self) -> None:
        self._queue.clear()
        self._generation = None
        self._last_sequence = None
        self._first_monotonic_ns = None
        self._first_captured_at = None

    def stop(self) -> None:
        with self._lock:
            self._reset()
            self._stopped = True

    @staticmethod
    def _age_ms(frame: _ReceivedFrame, now: datetime) -> int:
        return max(0, int((now - frame.received_at).total_seconds() * 1000))


class CameraNodeLiveTransport(Protocol):
    """One replaceable authenticated live-media transport boundary."""

    def iter_analysis_frames(self, *, maximum_frames: int) -> Iterator[AnalysisFrameEnvelope]: ...
    def request_evidence_burst(self, request: EvidenceBurstRequest) -> EvidenceBurstResult: ...
    def close(self) -> None: ...


class CameraNodeHttpTransport:
    """Bounded authenticated multipart-JPEG transport for one paired Camera Node."""

    boundary = b"mockingbird-analysis-frame"

    def __init__(
        self,
        *,
        base_address: str,
        credential: str,
        camera_id: str,
        stream_id: str,
        evidence_profile_id: str,
        maximum_frame_bytes: int = DEFAULT_MAXIMUM_FRAME_BYTES,
        response_timeout_seconds: float = 10.0,
    ) -> None:
        if (
            not credential
            or not camera_id
            or "/" in camera_id
            or not stream_id
            or not evidence_profile_id
            or "/" in evidence_profile_id
            or not 1024 <= maximum_frame_bytes <= 16_000_000
            or not 1 <= response_timeout_seconds <= 30
        ):
            raise ValueError("invalid_camera_node_live_transport")
        self.base_address = normalize_camera_node_address(base_address)
        self.credential = credential
        self.camera_id = camera_id
        self.stream_id = stream_id
        self.evidence_profile_id = evidence_profile_id
        self.maximum_frame_bytes = maximum_frame_bytes
        self.response_timeout_seconds = response_timeout_seconds
        self._connection: HTTPConnection | HTTPSConnection | None = None
        self._closed = False

    def iter_analysis_frames(self, *, maximum_frames: int) -> Iterator[AnalysisFrameEnvelope]:
        if self._closed or not 1 <= maximum_frames <= 1200:
            raise ValueError("invalid_analysis_stream_bound")
        url = f"{self.base_address}/node/v1/cameras/{self.camera_id}/analysis-stream"
        connection: HTTPConnection | HTTPSConnection | None = None
        try:
            connection, path = UrlLibCameraNodeRequester._connection(
                url, connect_timeout_seconds=2.0
            )
            self._connection = connection
            connection.request(
                "GET",
                path,
                headers={
                    "Accept": "multipart/x-mixed-replace",
                    "Authorization": f"Bearer {self.credential}",
                    "Cache-Control": "no-store",
                    "X-MockingBird-Max-Frames": str(maximum_frames),
                },
            )
            if connection.sock is not None:
                connection.sock.settimeout(self.response_timeout_seconds)
            response = connection.getresponse()
            if response.status == 401:
                raise CameraNodeClientError("authentication_rejected")
            if 300 <= response.status < 400:
                raise CameraNodeClientError("node_redirect_rejected")
            content_type = response.getheader("Content-Type", "").lower()
            if response.status != 200 or "multipart/x-mixed-replace" not in content_type:
                raise CameraNodeClientError("analysis_stream_unavailable")
            for _ in range(maximum_frames):
                line = response.readline(256)
                while line == b"\r\n":
                    line = response.readline(256)
                if not line:
                    return
                if line.rstrip() not in {b"--" + self.boundary, b"--" + self.boundary + b"--"}:
                    raise CameraNodeClientError("analysis_stream_invalid")
                if line.rstrip().endswith(b"--"):
                    return
                headers = self._read_part_headers(response)
                length = _bounded_int(headers, "content-length", 1, self.maximum_frame_bytes)
                payload = response.read(length)
                if len(payload) != length or response.read(2) != b"\r\n":
                    raise CameraNodeClientError("analysis_stream_invalid")
                yield _analysis_envelope(self.stream_id, headers, payload)
        except (socket.timeout, TimeoutError, OSError) as error:
            raise CameraNodeClientError("analysis_stream_unavailable") from error
        finally:
            self._connection = None
            if connection is not None:
                connection.close()

    def request_evidence_burst(self, request: EvidenceBurstRequest) -> EvidenceBurstResult:
        if self._closed:
            return EvidenceBurstResult(request.request_id, "failed", failure_code="transport_closed")
        if request.requested_profile_id != self.evidence_profile_id:
            return EvidenceBurstResult(
                request.request_id,
                "failed",
                failure_code="evidence_profile_mismatch",
            )
        url = f"{self.base_address}/node/v1/cameras/{self.camera_id}/evidence-burst"
        connection: HTTPConnection | HTTPSConnection | None = None
        try:
            connection, path = UrlLibCameraNodeRequester._connection(url, connect_timeout_seconds=2.0)
            body = json.dumps(
                {"request_id": request.request_id, "profile_id": self.evidence_profile_id, "frame_count": 1},
                separators=(",", ":"),
            ).encode("utf-8")
            connection.request(
                "POST", path, body=body,
                headers={
                    "Accept": "image/jpeg",
                    "Authorization": f"Bearer {self.credential}",
                    "Content-Type": "application/json",
                    "Cache-Control": "no-store",
                },
            )
            if connection.sock is not None:
                connection.sock.settimeout(self.response_timeout_seconds)
            response = connection.getresponse()
            headers = {name.lower(): value for name, value in response.getheaders()}
            if response.status == 401:
                return EvidenceBurstResult(request.request_id, "failed", failure_code="authentication_rejected")
            if response.status != 200:
                return EvidenceBurstResult(request.request_id, "failed", failure_code="evidence_burst_unavailable")
            length = response.length
            if length is None or not 1 <= length <= 16_000_000:
                return EvidenceBurstResult(request.request_id, "failed", failure_code="evidence_burst_invalid")
            payload = response.read(length)
            digest = sha256(payload).hexdigest()
            dimensions = _jpeg_dimensions(payload)
            captured = _parse_timestamp(headers.get("x-mockingbird-captured-at")) or datetime.now(UTC)
            generation = headers.get("x-mockingbird-provider-generation", "")
            if (
                len(payload) != length
                or dimensions is None
                or headers.get("x-mockingbird-burst-request") != request.request_id
                or headers.get("x-mockingbird-content-sha256") != digest
                or headers.get("x-mockingbird-shadow-only") != "true"
                or not generation
            ):
                return EvidenceBurstResult(request.request_id, "failed", failure_code="evidence_burst_invalid")
            alignment = "supported" if request.trigger_captured_at <= captured <= request.deadline_at else "uncertain"
            frame = EvidenceBurstFrame(
                sequence=_bounded_int(headers, "x-mockingbird-burst-sequence", 1, 8),
                captured_at=captured,
                width=dimensions[0],
                height=dimensions[1],
                content_type="image/jpeg",
                content_hash=digest,
                payload=payload,
                parent_frame_id=request.trigger_frame_id,
                provider_generation=generation,
                request_to_capture_ms=max(0, int((captured - request.trigger_captured_at).total_seconds() * 1000)),
                temporal_alignment=alignment,
            )
            return EvidenceBurstResult(request.request_id, "captured", (frame,))
        except (CameraNodeClientError, socket.timeout, TimeoutError, OSError):
            return EvidenceBurstResult(request.request_id, "failed", failure_code="evidence_burst_unavailable")
        finally:
            if connection is not None:
                connection.close()

    def close(self) -> None:
        self._closed = True
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    @staticmethod
    def _read_part_headers(response: object) -> dict[str, str]:
        headers: dict[str, str] = {}
        for _ in range(24):
            line = response.readline(512)
            if line == b"\r\n":
                return headers
            if not line or len(line) > 511 or b":" not in line:
                break
            raw_name, raw_value = line.decode("ascii", "strict").split(":", 1)
            name = raw_name.strip().lower()
            if not name.replace("-", "").isalnum() or name in headers:
                break
            headers[name] = raw_value.strip()
        raise CameraNodeClientError("analysis_stream_invalid")


@dataclass(frozen=True)
class LiveShadowStatus:
    state: str
    frames_processed: int
    detector_frames: int
    detector_observations: int
    active_tracks: int
    burst_requests: int
    burst_captures: int
    burst_failures: int
    stale_bursts: int
    provider_generation: str | None
    source: AnalysisSourceStatus
    detector_cadence_fps: float | None
    pending_inference: int
    median_burst_latency_ms: float | None
    production_proposal_authority: bool = False


class LiveCameraNodeShadowSession:
    """Orchestrate Node frames, CUDA tracking, and temporary burst evidence only."""

    def __init__(
        self,
        *,
        source: CameraNodeAnalysisSource,
        transport: CameraNodeLiveTransport,
        provider: FrameDrivenObservationProvider,
        evidence_profile_id: str,
        burst_deadline_ms: int = 10_000,
        minimum_burst_interval_ms: int = 1_000,
    ) -> None:
        if (
            not evidence_profile_id
            or not 500 <= burst_deadline_ms <= 30_000
            or not 0 <= minimum_burst_interval_ms <= 60_000
        ):
            raise ValueError("invalid_live_shadow_session")
        self.source = source
        self.transport = transport
        self.provider = provider
        self.evidence_profile_id = evidence_profile_id
        self.burst_deadline_ms = burst_deadline_ms
        self.minimum_burst_interval_ms = minimum_burst_interval_ms
        self._generation: str | None = None
        self._burst_generations: deque[str] = deque(maxlen=256)
        self._temporary_payloads: OrderedDict[str, bytes] = OrderedDict()
        self._burst_latencies_ms: deque[int] = deque(maxlen=128)
        self._last_burst_trigger_at: datetime | None = None
        self._frames_processed = 0
        self._burst_requests = 0
        self._burst_captures = 0
        self._burst_failures = 0
        self._stale_bursts = 0
        self._pending_inference = 0
        self._running = False

    def start(self) -> None:
        self.provider.start_live(self.source.stream_id)
        self._running = True

    async def process_envelope(
        self, envelope: AnalysisFrameEnvelope, *, received_at: datetime | None = None
    ) -> ObservationResult | None:
        if not self._running:
            raise ValueError("live_shadow_not_started")
        self.source.offer(envelope, received_at=received_at)
        frame = self.source.pop_latest(now=received_at)
        if frame is None:
            return None
        return await self._process_frame(frame)

    async def _process_frame(self, frame: FramePacket) -> ObservationResult:
        generation = frame.provider_generation
        if generation is None:
            raise ValueError("analysis_frame_generation")
        if self._generation is not None and generation != self._generation:
            self.provider.restart_live_generation(
                self.source.stream_id, "provider_generation_changed"
            )
            self._burst_generations.clear()
            self._temporary_payloads.clear()
        self._generation = generation
        self._pending_inference = 1
        try:
            result = await self.provider.observe_live_frame(frame)
        finally:
            self._pending_inference = 0
        self._frames_processed += 1
        burst_evidence: list[EvidenceCandidate] = []
        for update in result.track_updates:
            meaningful = update.lifecycle_state == "confirmed" or (
                update.confidence is not None
                and update.confidence >= self.provider.settings.strong_detection_threshold
            )
            if not meaningful or update.generation_id in self._burst_generations:
                continue
            trigger_at = frame.captured_at or datetime.now(UTC)
            if (
                self._last_burst_trigger_at is not None
                and (trigger_at - self._last_burst_trigger_at).total_seconds() * 1000
                < self.minimum_burst_interval_ms
            ):
                continue
            self._burst_generations.append(update.generation_id)
            self._last_burst_trigger_at = trigger_at
            self._burst_requests += 1
            request = EvidenceBurstRequest(
                request_id="shadow-burst:" + sha256(
                    f"{generation}:{update.generation_id}".encode()
                ).hexdigest()[:24],
                stream_id=frame.stream_id,
                node_session_id=frame.node_session_id or "unknown",
                track_generation_id=update.generation_id,
                trigger_frame_id=frame.frame_id or "unknown",
                trigger_captured_at=frame.captured_at or datetime.now(UTC),
                requested_frame_count=1,
                requested_profile_id=self.evidence_profile_id,
                cadence_ms=0,
                subject_geometry=update.bounding_box,
                zone_id=None,
                deadline_at=(frame.captured_at or datetime.now(UTC)) + timedelta(milliseconds=self.burst_deadline_ms),
            )
            burst = self.transport.request_evidence_burst(request)
            if burst.status != "captured":
                self._burst_failures += 1
                continue
            item = burst.frames[0]
            if (
                item.provider_generation != generation
                or request.track_generation_id != update.generation_id
                or item.parent_frame_id != request.trigger_frame_id
            ):
                self._stale_bursts += 1
                continue
            self._burst_captures += 1
            if item.request_to_capture_ms is not None:
                self._burst_latencies_ms.append(item.request_to_capture_ms)
            self._temporary_payloads[item.content_hash] = item.payload
            self._temporary_payloads.move_to_end(item.content_hash)
            while len(self._temporary_payloads) > 8:
                self._temporary_payloads.popitem(last=False)
            burst_evidence.append(EvidenceCandidate(
                media_asset_id=f"shadow-burst:{item.content_hash}",
                stream_id=frame.stream_id,
                role="high_resolution_burst",
                captured_at=item.captured_at,
                frame_id=request.trigger_frame_id,
                source_offset_ms=frame.source_offset_ms,
                width=item.width,
                height=item.height,
                subject_geometry=request.subject_geometry,
                track_generation_id=request.track_generation_id,
                detector_provenance="onnx-cuda",
                tracker_provenance=FRAME_DRIVEN_PROVIDER_VERSION,
                quality_facts=(
                    ("content_hash", item.content_hash),
                    ("temporal_alignment", item.temporal_alignment),
                    ("request_to_capture_ms", item.request_to_capture_ms),
                    ("track_supported", True),
                    ("track_active_at_capture", None),
                    ("subject_supported", None),
                    ("supporting_frame_count", len(update.supporting_frame_ids)),
                ),
                temporary=True,
                shadow_only=True,
            ))
        return replace(
            result, evidence_candidates=result.evidence_candidates + tuple(burst_evidence)
        )

    async def run(self, *, maximum_frames: int) -> tuple[ObservationResult, ...]:
        """Receive concurrently with inference and coalesce to bounded newest work."""
        import asyncio

        if not 1 <= maximum_frames <= 1200:
            raise ValueError("invalid_analysis_stream_bound")
        if not self._running:
            self.start()
        available = threading.Event()
        finished = threading.Event()
        errors: list[BaseException] = []

        def receive() -> None:
            try:
                for envelope in self.transport.iter_analysis_frames(maximum_frames=maximum_frames):
                    self.source.offer(envelope, received_at=datetime.now(UTC))
                    available.set()
            except BaseException as error:
                errors.append(error)
            finally:
                finished.set()
                available.set()

        receiver = threading.Thread(target=receive, name="camera-node-analysis-receiver", daemon=True)
        receiver.start()
        results: list[ObservationResult] = []
        try:
            while not finished.is_set() or self.source.status().queue_depth:
                await asyncio.to_thread(available.wait, 0.25)
                available.clear()
                frame = self.source.pop_latest()
                if frame is not None:
                    results.append(await self._process_frame(frame))
            if errors:
                raise errors[0]
            return tuple(results)
        finally:
            receiver.join(timeout=2.0)
            if receiver.is_alive():
                self.transport.close()
                receiver.join(timeout=2.0)

    def status(self) -> LiveShadowStatus:
        facts = self.provider.replay_semantic_facts()
        source = self.source.status()
        frames = int(facts.get("frames_supplied", 0))
        inferred = int(facts.get("frames_inferred", 0))
        cadence = None
        if source.actual_received_fps is not None and frames:
            cadence = round(source.actual_received_fps * inferred / frames, 3)
        latencies = sorted(self._burst_latencies_ms)
        median = None
        if latencies:
            middle = len(latencies) // 2
            median = float(latencies[middle]) if len(latencies) % 2 else (latencies[middle - 1] + latencies[middle]) / 2
        return LiveShadowStatus(
            "running" if self._running else "stopped",
            self._frames_processed,
            inferred,
            int(facts.get("detector_observations", 0)),
            self.provider.active_track_count,
            self._burst_requests,
            self._burst_captures,
            self._burst_failures,
            self._stale_bursts,
            self._generation,
            source,
            cadence,
            self._pending_inference,
            median,
        )

    def stop(self) -> tuple[ObservationResult, ...]:
        results: tuple[ObservationResult, ...] = ()
        failure: BaseException | None = None
        try:
            if self._running:
                results = self.provider.stop_live("live_shadow_stopped")
        except BaseException as error:
            failure = error
        finally:
            self.transport.close()
            self.source.stop()
            self._temporary_payloads.clear()
            self._burst_generations.clear()
            self._burst_latencies_ms.clear()
            self._generation = None
            self._pending_inference = 0
            self._last_burst_trigger_at = None
            self._running = False
        if failure is not None:
            raise failure
        return results


def _analysis_envelope(stream_id: str, headers: dict[str, str], payload: bytes) -> AnalysisFrameEnvelope:
    content_type = headers.get("content-type", "").lower()
    digest = sha256(payload).hexdigest()
    if content_type != "image/jpeg" or headers.get("x-mockingbird-content-sha256") != digest:
        raise CameraNodeClientError("analysis_stream_invalid")
    return AnalysisFrameEnvelope(
        stream_id=stream_id,
        node_session_id=_required_header(headers, "x-mockingbird-node-session"),
        sequence=_bounded_int(headers, "x-mockingbird-sequence", 0, 2_147_483_647),
        frame_id=_required_header(headers, "x-mockingbird-frame-id"),
        captured_at=_required_timestamp(headers, "x-mockingbird-captured-at"),
        source_monotonic_ns=_bounded_int(headers, "x-mockingbird-source-monotonic-ns", 0, 2**63 - 1),
        width=_bounded_int(headers, "x-mockingbird-width", 1, 16_000),
        height=_bounded_int(headers, "x-mockingbird-height", 1, 12_000),
        content_type=content_type,
        provider_generation=_required_header(headers, "x-mockingbird-provider-generation"),
        payload=payload,
        content_hash=digest,
        timing_facts=(("capture_timestamp", "supported"), ("source_monotonic", "supported")),
    )


def _required_header(headers: dict[str, str], name: str) -> str:
    value = headers.get(name, "")
    if not value or len(value) > 240 or "\r" in value or "\n" in value:
        raise CameraNodeClientError("analysis_stream_invalid")
    return value


def _bounded_int(headers: dict[str, str], name: str, minimum: int, maximum: int) -> int:
    value = _required_header(headers, name)
    try:
        parsed = int(value)
    except ValueError as error:
        raise CameraNodeClientError("analysis_stream_invalid") from error
    if not minimum <= parsed <= maximum:
        raise CameraNodeClientError("analysis_stream_invalid")
    return parsed


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value or len(value) > 80:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _required_timestamp(headers: dict[str, str], name: str) -> datetime:
    value = _parse_timestamp(_required_header(headers, name))
    if value is None:
        raise CameraNodeClientError("analysis_stream_invalid")
    return value


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(b"\xff\xd8"):
        return None
    index = 2
    while index + 9 < len(data):
        if data[index] != 0xFF:
            index += 1
            continue
        marker = data[index + 1]
        index += 2
        if marker in {0xD8, 0xD9}:
            continue
        if index + 2 > len(data):
            return None
        length = int.from_bytes(data[index:index + 2], "big")
        if length < 2 or index + length > len(data):
            return None
        if marker in {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}:
            return int.from_bytes(data[index + 5:index + 7], "big"), int.from_bytes(data[index + 3:index + 5], "big")
        index += length
    return None



def _valid_normalized_box(box: tuple[float, float, float, float]) -> bool:
    return (
        len(box) == 4
        and all(isinstance(value, (int, float)) and 0.0 <= value <= 1.0 for value in box)
        and box[0] < box[2]
        and box[1] < box[3]
    )
