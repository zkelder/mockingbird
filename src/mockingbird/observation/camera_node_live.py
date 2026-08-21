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
from typing import Callable, Iterator, Protocol

from mockingbird.observation.burst_scheduler import (
    RESET_GENERATION_REPLACEMENT,
    RESET_SESSION_STOP,
    BurstOpportunity,
    BurstScheduler,
    BurstSchedulerConfig,
    BurstSchedulerDiagnostics,
    BurstSchedulerHealth,
)
from mockingbird.observation.contracts import (
    CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
    EvidenceCandidate,
    FramePacket,
    ObservationResult,
)
from mockingbird.observation.frame_driven_provider import (
    FRAME_DRIVEN_PROVIDER_VERSION,
    FrameDrivenObservationProvider,
)
from mockingbird.observation.localization_attribution import (
    geometry_attribution_for_burst,
    geometry_attribution_for_update,
    geometry_source_from_support_state,
)
from mockingbird.observation.media_contracts import (
    AnalysisFrameEnvelope,
    EvidenceBurstFrame,
    EvidenceBurstRequest,
    EvidenceBurstResult,
)
from mockingbird.observation.session_timeline import native_reconnect_step
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
    # Stage 6.11B: transport-connection-segment facts, kept distinct from
    # `generation_resets` above (see docs/reconnect-continuity-contract.md's
    # "three separate concepts"). `transport_reconnect_count` is a lifetime
    # total of every distinct real HTTP connection observed, regardless of
    # whether provider_generation also changed; `current_connection_segment_
    # ordinal` is this source's own current position in that count, reset
    # to 0 only by a genuine generation change. Neither is cleared by an
    # ordinary benign reconnect.
    transport_reconnect_count: int = 0
    current_connection_segment_ordinal: int = -1


@dataclass(frozen=True)
class _ReceivedFrame:
    envelope: AnalysisFrameEnvelope
    received_at: datetime
    # Offer-time-authoritative segment ordinal (see
    # `CameraNodeAnalysisSource._segment_ordinal`): captured per envelope so
    # a later, possibly-coalesced pop reports the ordinal that was true when
    # *this* envelope actually arrived, not whatever the running counter has
    # advanced to by delivery time.
    segment_ordinal: int


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
        # Stage 6.11B: transport-connection-segment bookkeeping, kept
        # distinct from the observation-source-generation bookkeeping above
        # (see docs/reconnect-continuity-contract.md's "three separate
        # concepts"). `_node_session_id`/`_segment_ordinal` are updated at
        # OFFER time, in true wire arrival order: a genuine mid-connection
        # sequence anomaly is still caught by the monotonic check below --
        # only a real new HTTP connection (a new node_session_id)
        # legitimately restarts it.
        self._node_session_id: str | None = None
        self._segment_ordinal: int = -1
        # Lifetime diagnostic: every distinct real HTTP connection observed,
        # regardless of how its boundary is later classified. Never reset
        # by an ordinary generation change -- this counter answers "how
        # many times did the transport actually reconnect," not "how many
        # of those were judged benign" (that lives in the provider's own
        # `reconnect_bridges_attempted` fact; see `LiveReconnectDiagnostics`).
        self._transport_reconnect_count = 0
        # Delivered-stream bookkeeping (pop-time, coalescing-robust):
        # computed against the frame actually handed to a caller, never a
        # frame that was coalesced away, so `temporal_discontinuity`/the
        # session-relative offset below reflect exactly what the tracker
        # will see next -- never a transition invisible to it.
        self._delivered_segment_id: str | None = None
        self._delivered_received_at: datetime | None = None
        self._delivered_local_offset_ms: int = 0
        self._session_base_offset_ms: int = 0

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
        generation_changed = self._generation is not None and self._generation != envelope.provider_generation
        if self._generation is None or generation_changed:
            # A genuine observation-source reset: either the very first
            # frame ever offered, or a real provider_generation change.
            # Every anchor -- including the session-relative bookkeeping
            # `_pop_latest` maintains -- restarts fresh; a benign reconnect
            # below deliberately does not touch the session-relative side.
            if self._generation is not None:
                self._generation_resets += 1
            if self._node_session_id is not None and self._node_session_id != envelope.node_session_id:
                self._transport_reconnect_count += 1
            self._queue.clear()
            self._last_sequence = None
            self._first_monotonic_ns = envelope.source_monotonic_ns
            self._first_captured_at = envelope.captured_at
            self._generation = envelope.provider_generation
            self._node_session_id = envelope.node_session_id
            self._segment_ordinal = 0
            self._delivered_segment_id = None
            self._delivered_received_at = None
            self._delivered_local_offset_ms = 0
            self._session_base_offset_ms = 0
        elif envelope.node_session_id != self._node_session_id:
            # Stage 6.11B: a fresh HTTP connection under the SAME
            # provider_generation -- a benign transport reconnect, not proof
            # the camera/observation source changed. The Node's own
            # per-connection sequence header restarts at 1 (see
            # docs/session-timeline-contract.md), so only the
            # connection-local sequence/offset anchors reset here; this
            # must not force a full source rebuild the way it used to
            # (Stage 6.6-era `_CaptureLoop` behavior, removed in this
            # stage -- see docs/reconnect-continuity-contract.md).
            self._transport_reconnect_count += 1
            self._segment_ordinal += 1
            self._last_sequence = None
            self._first_monotonic_ns = envelope.source_monotonic_ns
            self._first_captured_at = envelope.captured_at
            self._node_session_id = envelope.node_session_id
        if self._last_sequence is not None:
            if envelope.sequence <= self._last_sequence:
                raise ValueError("analysis_frame_sequence")
            self._sequence_gaps += max(0, envelope.sequence - self._last_sequence - 1)
        self._last_sequence = envelope.sequence
        if len(self._queue) >= self.maximum_queue_frames:
            self._queue.popleft()
            self._dropped += 1
        self._queue.append(_ReceivedFrame(envelope, received, self._segment_ordinal))
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

        # Connection-local ("original") source offset: anchored per segment,
        # unchanged basis from before Stage 6.11B -- resets near zero at
        # every new connection segment exactly like the transport sequence
        # does (the "transport connection segment" definition in
        # docs/reconnect-continuity-contract.md), preserved unmodified as
        # separate provenance rather than discarded.
        if envelope.source_monotonic_ns is not None and self._first_monotonic_ns is not None:
            local_offset_ms = max(0, (envelope.source_monotonic_ns - self._first_monotonic_ns) // 1_000_000)
        elif self._first_captured_at is not None:
            local_offset_ms = max(0, int((envelope.captured_at - self._first_captured_at).total_seconds() * 1000))
        else:
            local_offset_ms = 0

        # Session-relative ("logical") offset: continuous across a benign
        # reconnect. Only the *step* across a genuine segment transition
        # uses host receive time (the only clock comparable across two
        # different connections, via the identical Stage 6.8 native-
        # timeline arithmetic `native_reconnect_step` exposes); within one
        # segment this tracks local_offset_ms exactly, preserving this
        # source's existing single-connection precision unchanged.
        discontinuity = self._delivered_segment_id is not None and envelope.node_session_id != self._delivered_segment_id
        if self._delivered_segment_id is None:
            uncertainty_ms = 0
        elif discontinuity:
            assert self._delivered_received_at is not None
            step_ms, uncertainty_ms = native_reconnect_step(
                previous_received_at=self._delivered_received_at, current_received_at=newest.received_at,
            )
            self._session_base_offset_ms += self._delivered_local_offset_ms + step_ms
        else:
            uncertainty_ms = 0
        session_offset_ms = self._session_base_offset_ms + local_offset_ms
        self._delivered_segment_id = envelope.node_session_id
        self._delivered_received_at = newest.received_at
        self._delivered_local_offset_ms = local_offset_ms

        return FramePacket(
            stream_id=envelope.stream_id,
            media_asset_id=f"shadow-frame:{envelope.frame_id}",
            captured_at=envelope.captured_at,
            frame_id=envelope.frame_id,
            source_offset_ms=session_offset_ms,
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
                # Stage 6.11B provenance consumed by
                # `reconnect_continuity.classify_frame_reconnect_boundary`
                # and by `LiveCameraNodeShadowSession`'s cross-segment
                # track-span diagnostic -- present on every delivered frame,
                # not only a discontinuous one, so segment identity/order
                # remains visible provenance throughout (never discarded).
                ("original_source_offset_ms", local_offset_ms),
                ("connection_segment_id", envelope.node_session_id),
                ("connection_segment_ordinal", newest.segment_ordinal),
                ("temporal_discontinuity", discontinuity),
                ("temporal_uncertainty_ms", uncertainty_ms),
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
            self._transport_reconnect_count,
            self._segment_ordinal,
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
        # Transient, in-flight transport-segment state -- cleared exactly
        # like the anchors above. `_transport_reconnect_count` is
        # deliberately NOT cleared here: it is a lifetime diagnostic (see
        # its own docstring in `__init__`), matching how `_generation_resets`/
        # `_received`/`_delivered` already survive a reset.
        self._node_session_id = None
        self._segment_ordinal = -1
        self._delivered_segment_id = None
        self._delivered_received_at = None
        self._delivered_local_offset_ms = 0
        self._session_base_offset_ms = 0

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


def _classify_analysis_stream_transport_error(error: BaseException) -> str:
    """Bounded, safe (a fixed vocabulary word, never raw host/port/message
    text) classification of the low-level socket/connection failure behind
    one `analysis_stream_unavailable` -- Camera Node Connectivity & Recovery
    Diagnosis v1 (real 2026-08-20 field incident: the host-side API alone
    could not tell "Camera Node refused the connection" apart from "it timed
    out," and no Pi-side log access existed to fill that gap). Purely
    additive: never changes what `analysis_stream_unavailable` itself means
    or how the caller's bounded retry policy treats it -- see
    `AnalysisStreamRetryPolicy`."""

    if isinstance(error, ConnectionRefusedError):
        return "connect_refused"
    if isinstance(error, ConnectionResetError):
        return "connection_reset"
    if isinstance(error, (socket.timeout, TimeoutError)):
        return "timeout"
    if isinstance(error, socket.gaierror):
        return "dns_unresolved"
    return "os_error"


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
            if response.status != 200:
                raise CameraNodeClientError("analysis_stream_unavailable", failure_class="http_status")
            if "multipart/x-mixed-replace" not in content_type:
                raise CameraNodeClientError("analysis_stream_unavailable", failure_class="content_type_mismatch")
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
            raise CameraNodeClientError(
                "analysis_stream_unavailable",
                failure_class=_classify_analysis_stream_transport_error(error),
            ) from error
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
class LiveReconnectDiagnostics:
    """Bounded, read-only Stage 6.11B reconnect-continuity diagnostics for
    one live Camera Node shadow session. A status read starts nothing --
    every field is a snapshot of already-recorded, bounded state.

    `transport_reconnect_count` is a transport-level fact (every distinct
    real HTTP connection the analysis source has observed, from
    `AnalysisSourceStatus`); `benign_reconnect_count`/`reconnect_bridges_
    attempted` are the same underlying provider-level count
    (`reconnect_bridges_attempted` in `FrameDrivenObservationProvider.
    replay_semantic_facts()`) named twice deliberately -- once for "how many
    reconnects were judged benign" and once matching the established
    replay-report field name -- so a reader familiar with either vocabulary
    finds what they expect.
    """

    transport_reconnect_count: int
    benign_reconnect_count: int
    true_reset_count: int
    insufficient_provenance_reset_count: int
    reconnect_bridges_attempted: int
    reconnect_bridges_continued: int
    reconnect_bridges_expired: int
    tracks_spanning_connection_segments: int
    current_connection_segment_ordinal: int
    last_reconnect_classification: str | None


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
    scheduler_diagnostics: BurstSchedulerDiagnostics | None = None
    scheduler_health: BurstSchedulerHealth | None = None
    reconnect_diagnostics: LiveReconnectDiagnostics | None = None


class LiveCameraNodeShadowSession:
    """Orchestrate Node frames, CUDA tracking, and temporary burst evidence only.

    Burst *opportunities* (a meaningful `TrackUpdate`) are advisory to the
    Stage 6.9 `BurstScheduler`, which decides whether to actually attempt a
    burst -- a new track generation alone no longer guarantees one. See
    docs/burst-scheduler-contract.md.
    """

    def __init__(
        self,
        *,
        source: CameraNodeAnalysisSource,
        transport: CameraNodeLiveTransport,
        provider: FrameDrivenObservationProvider,
        evidence_profile_id: str,
        burst_deadline_ms: int = 10_000,
        minimum_burst_interval_ms: int = 1_000,
        scheduler: BurstScheduler | None = None,
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
        # A caller may supply a pre-built scheduler (for example to share one
        # explicit BurstSchedulerConfig across a whole capture run); absent
        # that, default one from this session's own bounds so existing
        # callers that only set minimum_burst_interval_ms keep the same
        # effective per-generation cooldown as before this stage.
        self.scheduler = scheduler or BurstScheduler(
            session_id=f"live-shadow:{source.stream_id}",
            config=BurstSchedulerConfig(minimum_burst_interval_ms=minimum_burst_interval_ms),
        )
        self._generation: str | None = None
        self._temporary_payloads: OrderedDict[str, bytes] = OrderedDict()
        # Same-Frame Species Evidence v1 (see docs/same-frame-species-
        # evidence-contract.md): a second, independently-bounded temporary
        # cache mirroring `_temporary_payloads` exactly, but for the exact
        # analysis-stream frame that produced a burst-triggering track
        # update's own subject box -- the one place those real bytes are
        # ever seen before this method returns and the `FramePacket` goes
        # out of scope (see `_process_frame` below). `_same_frame_captured_
        # generations` bounds capture to at most once per track generation,
        # cleared alongside the payload cache on every generation reset so
        # neither grows across a genuine source-generation change.
        self._same_frame_temporary_payloads: OrderedDict[str, bytes] = OrderedDict()
        self._same_frame_captured_generations: set[str] = set()
        self._burst_latencies_ms: deque[int] = deque(maxlen=128)
        self._frames_processed = 0
        self._burst_requests = 0
        self._burst_captures = 0
        self._burst_failures = 0
        self._stale_bursts = 0
        self._pending_inference = 0
        self._running = False
        # Stage 6.11B: bounded, live-computed "does a track generation span
        # more than one connection segment" bookkeeping -- the live
        # counterpart of replay's `tracks_spanning_multiple_connection_
        # segments` metric (see `replay._reconnect_metrics`), computed
        # incrementally here since a live session has no complete retained
        # frame list to cross-reference after the fact. Bounded by active
        # generations only: an entry is removed the moment its generation
        # ends, so this cannot grow across a long-running session.
        self._generation_segments: dict[str, set[str]] = {}
        self._tracks_spanning_segments_count = 0

    def start(self) -> None:
        self.provider.start_live(self.source.stream_id)
        self._running = True

    def temporary_burst_payload(self, content_hash: str) -> bytes | None:
        """Bounded, read-only lookup into this session's own most-recent-8
        successfully captured evidence-burst payloads (see
        `_temporary_payloads` above), keyed by content hash.

        `EvidenceCandidate` is a provider-neutral fact record with no
        payload field, so a caller downstream of `process_envelope`/`run`
        (a temporal-capture retention loop, for instance) has no other way
        to recover the real bytes a captured burst already fetched from the
        Camera Node -- this is that one bounded, explicit path, never a
        fresh request of its own. Returns `None` once the entry has aged out
        of the bounded cache; a caller must never substitute unrelated bytes
        when that happens."""

        return self._temporary_payloads.get(content_hash)

    def temporary_same_frame_payload(self, content_hash: str) -> bytes | None:
        """Bounded, read-only lookup into this session's own most-recent-8
        captured same-frame classifier-evidence payloads (Same-Frame Species
        Evidence v1), mirroring `temporary_burst_payload` exactly -- the one
        other bounded temporary cache this session already exposes for the
        identical reason (`EvidenceCandidate` carries no payload field)."""

        return self._same_frame_temporary_payloads.get(content_hash)

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
        self._generation = generation
        self._pending_inference = 1
        # Stage 6.11B: the provider itself now classifies every reconnect
        # boundary (benign transport reconnect vs. genuine source-generation
        # reset) through the identical Stage 6.11 decision contract -- see
        # `FrameDrivenObservationProvider.observe_live_frame`. This session
        # no longer makes its own ad hoc "provider_generation changed"
        # judgment; it only reacts, afterward, to whether a reset actually
        # happened (compared by a before/after count rather than a
        # clear-on-read flag, so it cannot miss or double-count one reset).
        resets_before = self.provider.live_reset_count
        try:
            result = await self.provider.observe_live_frame(frame)
        finally:
            self._pending_inference = 0
        if self.provider.live_reset_count != resets_before:
            # A genuine source-generation reset (or an insufficient-
            # provenance safety reset) just happened inside the provider for
            # this exact frame -- mirror the pre-Stage-6.11B outer
            # session-level reset side effects (temporary burst payload
            # cache, scheduler state) exactly. A benign bridge, in contrast,
            # leaves both alone: recurrence-group/novelty state surviving a
            # benign reconnect is the entire point of the Stage 6.9 burst
            # scheduler (see docs/burst-scheduler-contract.md) -- resetting
            # it on every ordinary reconnect would defeat that stage's own
            # fix the same way the pre-6.11B tracker reset did.
            self._temporary_payloads.clear()
            self._same_frame_temporary_payloads.clear()
            self._same_frame_captured_generations.clear()
            self.scheduler.reset(RESET_GENERATION_REPLACEMENT)
            self._generation_segments.clear()
        self._frames_processed += 1
        segment_id = frame.node_session_id
        for update in result.track_updates:
            if segment_id:
                segments = self._generation_segments.setdefault(update.generation_id, set())
                if segment_id not in segments:
                    segments.add(segment_id)
                    if len(segments) == 2:
                        self._tracks_spanning_segments_count += 1
            if update.status == "ended":
                self._generation_segments.pop(update.generation_id, None)
        burst_evidence: list[EvidenceCandidate] = []
        for update in result.track_updates:
            meaningful = update.lifecycle_state == "confirmed" or (
                update.confidence is not None
                and update.confidence >= self.provider.settings.strong_detection_threshold
            )
            if not meaningful:
                continue
            # A track generation is a burst *opportunity*, not authority: the
            # scheduler -- not generation-id-seen-before bookkeeping -- decides
            # whether this specific moment is issued, a suppressed duplicate of
            # recent recurring geometry, deferred, or an override.
            opportunity = BurstOpportunity(
                opportunity_id=f"live-opportunity:{update.generation_id}:{frame.frame_id or frame.frame_sequence}",
                stream_id=frame.stream_id,
                session_id=self.scheduler.session_id,
                track_generation_id=update.generation_id,
                trigger_frame_id=frame.frame_id or "unknown",
                source_offset_ms=frame.source_offset_ms or 0,
                broad_class=update.broad_class or "animal",
                node_session_id=frame.node_session_id,
                provider_generation=generation,
                subject_geometry=update.bounding_box,
                detector_score=update.confidence,
                detector_confirmation_count=update.detector_confirmation_count,
                tracker_support_count=update.tracker_support_count,
                trigger_reason="shadow_track_event",
                requested_evidence_profile=self.evidence_profile_id,
            )
            decision = self.scheduler.decide(opportunity)
            if not decision.should_issue:
                continue
            self._burst_requests += 1
            request = EvidenceBurstRequest(
                request_id=decision.request_id,
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
                self.scheduler.record_result(decision.request_id, status="failed", failure_code=burst.failure_code)
                continue
            item = burst.frames[0]
            if (
                item.provider_generation != generation
                or request.track_generation_id != update.generation_id
                or item.parent_frame_id != request.trigger_frame_id
            ):
                self._stale_bursts += 1
                self.scheduler.record_result(decision.request_id, status="stale")
                continue
            self._burst_captures += 1
            if item.request_to_capture_ms is not None:
                self._burst_latencies_ms.append(item.request_to_capture_ms)
            self.scheduler.record_result(
                decision.request_id, status="captured",
                byte_size=len(item.payload), latency_ms=item.request_to_capture_ms,
            )
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
                # Localization Attribution / Detection Geometry Lineage v1
                # (see docs/localization-attribution-contract.md): `request.
                # subject_geometry` above is `update.bounding_box` at the
                # moment this burst was *requested* -- a genuinely separate,
                # later real capture (`item`, timed by the transport itself)
                # is what actually gets persisted as this candidate's image.
                # `request_to_capture_ms` is the exact, already-measured
                # round-trip the transport computed from two real
                # timestamps; reused here rather than re-derived.
                geometry_attribution=geometry_attribution_for_burst(
                    update, request_to_capture_ms=item.request_to_capture_ms,
                ),
            ))
            # Same-Frame Species Evidence v1 (see docs/same-frame-species-
            # evidence-contract.md): persist at most one exact analysis-
            # stream frame per track generation, alongside -- never instead
            # of -- the high-resolution burst above. Gated on the burst's
            # own success: a generation whose burst never captures cannot
            # be admitted as a Visit anyway (no `CandidateEvidenceItem` is
            # ever built without real backing bytes for an `identification`/
            # `context` pick -- see `candidate_visit_adapter.
            # _build_evidence_items`), so a same-frame asset would only ever
            # be orphaned evidence for a Visit that does not exist.
            #
            # `frame` here is the exact, real, already-decoded analysis
            # frame this loop iteration's `update` was itself produced from
            # this same `_process_frame` call -- never re-fetched, never a
            # different capture. Eligibility is proven, not assumed:
            # `geometry_source_from_support_state` returns `"detector"`/
            # `"tracker"` only for a support_state freshly (re)established
            # THIS exact frame, never `"carried_forward"` (a stale, coasting
            # box) -- `frame.frame_id == update.frame_id` alone is not
            # sufficient proof, because `frame_tracker._update` stamps the
            # current frame's own id onto every `TrackUpdate` regardless of
            # support_state (including a carried-forward one); the
            # support_state check is the actual freshness proof.
            if (
                update.generation_id not in self._same_frame_captured_generations
                and update.bounding_box is not None
                and frame.payload is not None
                and frame.frame_id is not None
                and frame.width is not None
                and frame.height is not None
                and update.frame_id == frame.frame_id
                and geometry_source_from_support_state(update.support_state) in ("detector", "tracker")
            ):
                same_frame_hash = sha256(frame.payload).hexdigest()
                self._same_frame_temporary_payloads[same_frame_hash] = frame.payload
                self._same_frame_temporary_payloads.move_to_end(same_frame_hash)
                while len(self._same_frame_temporary_payloads) > 8:
                    self._same_frame_temporary_payloads.popitem(last=False)
                self._same_frame_captured_generations.add(update.generation_id)
                burst_evidence.append(EvidenceCandidate(
                    media_asset_id=f"shadow-same-frame:{same_frame_hash}",
                    stream_id=frame.stream_id,
                    role=CLASSIFIER_SAME_FRAME_EVIDENCE_ROLE,
                    captured_at=frame.captured_at,
                    frame_id=frame.frame_id,
                    source_offset_ms=frame.source_offset_ms,
                    width=frame.width,
                    height=frame.height,
                    subject_geometry=update.bounding_box,
                    track_generation_id=update.generation_id,
                    detector_provenance="onnx-cuda",
                    tracker_provenance=FRAME_DRIVEN_PROVIDER_VERSION,
                    quality_facts=(
                        ("content_hash", same_frame_hash),
                        ("temporal_alignment", "same_frame"),
                        ("track_supported", True),
                        ("track_active_at_capture", True),
                        ("subject_supported", None),
                        ("supporting_frame_count", len(update.supporting_frame_ids)),
                    ),
                    temporary=True,
                    shadow_only=True,
                    source_capture_frame_id=frame.source_capture_frame_id,
                    source_content_hash=frame.source_content_hash,
                    # This is the one place in the live pipeline where the
                    # evidence image and the geometry's own source
                    # observation are provably the same captured frame --
                    # `same_frame=True` is earned by the eligibility check
                    # above, never assumed from a small measured gap.
                    geometry_attribution=geometry_attribution_for_update(
                        update, same_frame=True, evidence_source_offset_ms=frame.source_offset_ms,
                    ),
                ))
        return replace(
            result, evidence_candidates=result.evidence_candidates + tuple(burst_evidence)
        )

    async def run(
        self,
        *,
        maximum_frames: int,
        on_result: Callable[[ObservationResult], None] | None = None,
    ) -> tuple[ObservationResult, ...]:
        """Receive concurrently with inference and coalesce to bounded newest work.

        `on_result`, when supplied, is called synchronously with each
        frame's `ObservationResult` the instant it is produced -- before
        this method goes on to receive/process this batch's next frame --
        never batched until the whole call returns. This exists for a
        caller that must rescue a just-captured burst/same-frame payload
        out of this session's own bounded, content-hash-keyed temporary
        cache (`_temporary_payloads`/`_same_frame_temporary_payloads`,
        capped independently of any caller-side cache) before a *later*
        capture *within this same batch* has a chance to evict it: a batch
        can span `maximum_frames` frames, several of which can each
        independently capture a burst (concurrent generations, or several
        distinct subjects in sequence), so waiting for this whole method to
        return before harvesting -- the pre-existing behavior when
        `on_result` is omitted -- lets an early capture in a busy batch be
        evicted before any caller-side harvest ever sees it, even though a
        much larger caller-side cache still has ample headroom. See
        `engine_runtime._harvest_burst_bytes`, its own call site in
        `_run_async`, and docs/candidate-visit-authority-contract.md
        "Evidence-cache capacity" for the full mechanism this closes."""
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
                    result = await self._process_frame(frame)
                    results.append(result)
                    if on_result is not None:
                        on_result(result)
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
            scheduler_diagnostics=self.scheduler.diagnostics(),
            scheduler_health=self.scheduler.health(),
            reconnect_diagnostics=self._reconnect_diagnostics(facts, source),
        )

    def _reconnect_diagnostics(
        self, facts: dict[str, int], source: AnalysisSourceStatus,
    ) -> LiveReconnectDiagnostics:
        decision = self.provider.last_reconnect_decision
        return LiveReconnectDiagnostics(
            transport_reconnect_count=source.transport_reconnect_count,
            benign_reconnect_count=facts.get("reconnect_bridges_attempted", 0),
            true_reset_count=facts.get("resets_true_source_change", 0),
            insufficient_provenance_reset_count=facts.get("resets_insufficient_provenance", 0),
            reconnect_bridges_attempted=facts.get("reconnect_bridges_attempted", 0),
            reconnect_bridges_continued=facts.get("reconnect_bridges_continued", 0),
            reconnect_bridges_expired=facts.get("reconnect_bridges_expired", 0),
            tracks_spanning_connection_segments=self._tracks_spanning_segments_count,
            current_connection_segment_ordinal=source.current_connection_segment_ordinal,
            last_reconnect_classification=decision.decision if decision is not None else None,
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
            self._same_frame_temporary_payloads.clear()
            self._same_frame_captured_generations.clear()
            self._burst_latencies_ms.clear()
            self._generation = None
            self._pending_inference = 0
            self.scheduler.reset(RESET_SESSION_STOP)
            self._generation_segments.clear()
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
