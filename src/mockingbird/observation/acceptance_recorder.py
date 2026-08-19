"""Independent biological-encounter denominator recorder (Visit Authority
Budget + Ambiguous-Boundary Recall Closure v1).

Problem this exists to solve: the immediately preceding field session could
not establish a truly independent record of real animal activity, because
the Observation Engine holds exclusive capture ownership of the paired
Camera Node while running (the legacy live-view "current frame" endpoint
returns 409 during an active session) -- there was no way to look at the
same scene at the same time without going through the very pipeline being
evaluated. Using created Visits, detector tracks, proposals, or
counterfactual detections as the encounter denominator would answer "what
did the pipeline notice" circularly, never "what was actually there."

This module is the smallest bounded fix: a capability-safe tee, not a
second capture connection. `_EngineSession` (engine_runtime.py) already
decodes every analysis frame it receives from the paired Camera Node for
inference -- exactly the frames Observation itself uses, with no new
capture lock, no second consumer competing for the physical camera, and no
influence whatsoever on any detection/tracking/admission decision (this
module is never imported by, and never imports, `candidate_visit_
authority`/`candidate_quality_gate`/`visit_episode_assembler`/`mockingbird.
repository` -- it cannot become evidence or truth even by accident). A
bounded, bandwidth-conscious sample of those already-decoded bytes is
copied to a local, clearly-diagnostic-only directory with enough per-frame
identity (source-relative offset, wall-clock capture time, sequence index)
for a human reviewer to later scrub through and independently mark
encounter start/end and species/taxon -- without ever being shown what the
detector/tracker/admission pipeline concluded about the same moment.

Off by default; enabled only via `MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR` (see
`main.get_observation_engine_session_manager`) for an explicitly-scoped
field-validation session -- never a normal product capability, matching
"do not create a large recording subsystem." Never reused as evidence: no
MediaAsset, Visit, Event, DetectionProposal, or ReviewLabel is created by
this module under any input.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
from pathlib import Path
from typing import Protocol, runtime_checkable

ACCEPTANCE_RECORDER_VERSION = "acceptance-recorder-v1"

# Directory-listing env var read only by `main.get_observation_engine_
# session_manager` -- kept here, next to the recorder it configures, rather
# than scattered across the API layer (mirrors `engine_runtime.
# PROVIDER_CONFIG_PATH_ENV`'s own "the env var name lives with the thing it
# configures" convention).
ACCEPTANCE_RECORDING_DIR_ENV = "MOCKINGBIRD_ACCEPTANCE_RECORDING_DIR"


@runtime_checkable
class RecordableFrame(Protocol):
    """The only shape this module needs from a frame -- deliberately a
    structural `Protocol`, not an import of `contracts.FramePacket`, so a
    test double never needs the full engine-side type. `contracts.
    FramePacket` already satisfies this shape unchanged."""

    frame_id: str | None
    source_offset_ms: int | None
    captured_at: datetime | None
    payload: bytes | None


@dataclass(frozen=True)
class AcceptanceRecorderConfig:
    """Explicit, bounded, caller-configurable recording policy -- generous
    enough to catch a multi-minute encounter's own start/end at reasonable
    temporal resolution, small enough to stay a genuinely bounded diagnostic
    artifact, never an unbounded capture of the whole analysis stream.

    Defaults chosen for a real bounded field session (comparable to the
    ~98-minute 2026-08-19 session this milestone's own field defect was
    found in): a 3-second sample interval over 120 minutes yields at most
    2400 frames; each analysis-resolution JPEG is typically well under
    200KB (a fraction of a source-resolution evidence burst), so
    `max_total_bytes`'s own default (750MB) is reached only if frames run
    unusually large, not under ordinary operation -- both bounds are
    enforced directly, never assumed.
    """

    output_dir: Path
    sample_interval_ms: int = 3_000
    max_frames: int = 2_400
    max_total_bytes: int = 750_000_000

    def __post_init__(self) -> None:
        if self.sample_interval_ms < 100:
            raise ValueError("invalid_acceptance_recorder_interval")
        if not 1 <= self.max_frames <= 100_000:
            raise ValueError("invalid_acceptance_recorder_frame_bound")
        if not 1_000_000 <= self.max_total_bytes <= 5_000_000_000:
            raise ValueError("invalid_acceptance_recorder_byte_bound")


@dataclass(frozen=True)
class AcceptanceRecorderStatus:
    """Bounded, read-only accounting -- surfaced in the final field report,
    never in ordinary product status/health (this tool is not a product
    capability)."""

    frames_considered: int
    frames_saved: int
    frames_skipped_interval: int
    total_bytes_saved: int
    stopped_reason: str | None
    manifest_path: str


class BoundedFrameSampleRecorder:
    """Samples already-decoded analysis frames at a bounded cadence and
    writes them, plus a companion JSONL manifest (one line per saved frame:
    sequence index, source-relative offset, wall-clock capture time,
    filename, sha256 content hash), to `config.output_dir`.

    Every decision is local and synchronous -- no network call, no product-
    repository import, no background thread of its own (the caller's own
    existing frame-processing loop drives it, exactly like `_harvest_burst_
    bytes` already drives the burst-evidence cache). A frame with no
    payload, no source offset, or no capture time is honestly skipped
    (never fabricated), and skip reasons are counted, never silently
    dropped -- see `AcceptanceRecorderStatus`."""

    def __init__(self, config: AcceptanceRecorderConfig) -> None:
        self._config = config
        self._output_dir = config.output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._manifest_path = self._output_dir / "manifest.jsonl"
        self._last_saved_offset_ms: int | None = None
        self._frames_considered = 0
        self._frames_saved = 0
        self._frames_skipped_interval = 0
        self._total_bytes_saved = 0
        self._stopped_reason: str | None = None

    @property
    def is_accepting(self) -> bool:
        return self._stopped_reason is None

    def maybe_record(self, frame: RecordableFrame) -> bool:
        """Consider one already-decoded frame. Returns whether it was
        actually saved. Never raises: a malformed frame is honestly skipped,
        exactly like every other bounded diagnostic mechanism in this
        package (`_harvest_burst_bytes`, `CounterfactualLedger`)."""

        if not self.is_accepting:
            return False
        self._frames_considered += 1
        if not frame.payload or frame.source_offset_ms is None or frame.captured_at is None:
            return False
        if (
            self._last_saved_offset_ms is not None
            and frame.source_offset_ms - self._last_saved_offset_ms < self._config.sample_interval_ms
        ):
            self._frames_skipped_interval += 1
            return False
        if self._frames_saved >= self._config.max_frames:
            self._stopped_reason = "max_frames_reached"
            return False
        if self._total_bytes_saved + len(frame.payload) > self._config.max_total_bytes:
            self._stopped_reason = "max_total_bytes_reached"
            return False

        digest = sha256(frame.payload).hexdigest()
        filename = f"frame-{self._frames_saved:06d}-offset{frame.source_offset_ms:09d}ms.jpg"
        (self._output_dir / filename).write_bytes(frame.payload)
        record = {
            "sequence": self._frames_saved,
            "frame_id": frame.frame_id,
            "source_offset_ms": frame.source_offset_ms,
            "captured_at": frame.captured_at.isoformat(),
            "filename": filename,
            "content_hash": digest,
            "byte_count": len(frame.payload),
        }
        with self._manifest_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

        self._last_saved_offset_ms = frame.source_offset_ms
        self._frames_saved += 1
        self._total_bytes_saved += len(frame.payload)
        return True

    def status(self) -> AcceptanceRecorderStatus:
        return AcceptanceRecorderStatus(
            frames_considered=self._frames_considered,
            frames_saved=self._frames_saved,
            frames_skipped_interval=self._frames_skipped_interval,
            total_bytes_saved=self._total_bytes_saved,
            stopped_reason=self._stopped_reason,
            manifest_path=str(self._manifest_path),
        )
