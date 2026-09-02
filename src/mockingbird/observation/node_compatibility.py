"""Host <-> Camera Node Release-Compatibility Preflight v1: a single, bounded,
capability-based answer to "is this Host and this Camera Node compatible for
the capability this Host intends to use right now" -- built because
Representative Daylight Gate A Field Acceptance v8 ran a full 158-minute
field session against a real reference Camera Node whose installed software
(69 commits behind) predated the accepted RTT-Bounded Clock Calibration v1
protocol, producing 796 calibration attempts and 0 valid samples, discovered
only after the session had already run. See
docs/host-camera-node-release-compatibility-preflight-v1-report.md.

**Compatibility is capability-based, never exact-commit equality.** A Node
whose source commit differs from Host HEAD is routinely, correctly,
compatible -- see `provider_compatibility.py`'s own precedent for "one
bounded, truthful classification, never guessed." The one thing this module
deliberately does *not* do is compare `git_commit` values: the Camera Node's
own `/node/v1/health` response has never exposed one (only a package
`service_version`, itself unrelated to source-commit distance -- see
`camera_node.git_commit` in the milestone report's "Version-skew behavior"
for why that remains a diagnostic field, never a gate). The existing
`api_version` exact-match gate (`CameraNodeClient.pair`,
`camera_node_transport.TRANSPORT_PROTOCOL_VERSION`) already fully protects
wire-protocol-shape compatibility at pairing/transport time; this module
answers a narrower, additive question a *paired* Node can still fail:
does it support the specific capabilities a particular Host operation
requires, right now.

Two bounded profiles (Section 8 of the governing milestone brief), not a
general-purpose fleet-capability system -- reuse the existing concept if a
third one is ever genuinely needed rather than growing this list casually:

- ``"ordinary_monitoring"``: everyday product use. Only requires the Node's
  health protocol to answer at all. An old, pre-RTT Node (exactly v8's real
  Node) is, correctly, compatible here -- RTT-bounded clock calibration is
  an optional diagnostic capability for this profile, never a blocker (see
  product-doctrine.md "Capability-aware UX": unsupported features are
  honestly absent, not a reason to refuse ordinary service).
- ``"field_acceptance"``: a Representative Daylight Gate A / true-latency
  acceptance session, which cannot honestly measure T0->T5 latency without
  a real, valid, bounded RTT clock calibration. Requires the paired camera
  to be live-confirmed available and a *real* bounded RTT probe -- run with
  the exact accepted `clock_calibration.estimate_rtt_clock_calibration`
  function, never a second implementation (Section 20) -- to actually
  succeed, not merely advertise the right response fields.

No wire-protocol change was needed or made: `node_receive_time`/`node_time`
(RTT-Bounded Clock Calibration v1) and `api_version`/`service_version`
(already existing) are sufficient to answer every question this profile
pair asks. An old Node's response continues to parse exactly as it always
has (`CameraNodeClient.health`/`sample_clock_round_trip` already degrade
absent fields to `None`, never raise) -- absence of a field means capability
unavailable/unknown here, never a parser failure.

Pure and dependency-light where the decision itself is concerned
(`classify_node_compatibility`), matching this package's established "pure
decision module" convention (see `provider_compatibility.py`,
`clock_calibration.estimate_rtt_clock_calibration`) -- the live network
orchestration (`probe_node_compatibility`) is a thin, separately-testable
shell around it, reusing `CameraNodeClient`/`estimate_rtt_clock_calibration`
unchanged rather than re-implementing either."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from mockingbird.observation.clock_calibration import (
    RttClockCalibrationRecord,
    RttRoundTrip,
    estimate_rtt_clock_calibration,
)
from mockingbird.source_providers.camera_node import CameraNodeClient, CameraNodeClientError

CompatibilityProfile = Literal["ordinary_monitoring", "field_acceptance"]

NodeCompatibilityState = Literal[
    "compatible",
    "incompatible_missing_capability",
    "incompatible_protocol",
    "calibration_failed",
    "node_unreachable",
    "camera_unavailable",
]

#: A bounded real batch, not a recurring poll (Section 26) -- mirrors
#: `engine_runtime._RTT_CALIBRATION_BATCH_SIZE` exactly (kept as its own
#: named constant here rather than imported: this codebase already
#: deliberately duplicates small cross-package tuning/version constants
#: rather than reaching into another module's private name -- see
#: `NODE_API_VERSION`'s own documented precedent in `doctor.py`).
DEFAULT_FIELD_ACCEPTANCE_RTT_PROBE_BATCH_SIZE = 5

#: Curated, disclosed, one-place REQUIRED-capability declaration for each
#: profile (Section 7/8). A capability absent from a profile's own tuple is
#: OPTIONAL for that profile -- its absence is reported (when observed) but
#: never causes that profile to be judged incompatible. Do not add a
#: capability here merely to look complete (Section 7's own explicit
#: warning) -- each entry must correspond to a real, already-identified
#: Host requirement.
REQUIRED_CAPABILITIES: Mapping[CompatibilityProfile, tuple[str, ...]] = {
    "ordinary_monitoring": ("health_protocol",),
    "field_acceptance": (
        "health_protocol",
        "expected_camera_available",
        "rtt_timestamp_fields",
        "bounded_rtt_clock_calibration",
    ),
}

_MESSAGES: Mapping[NodeCompatibilityState, str] = {
    "compatible": "Camera Node is compatible for this operation.",
    "incompatible_missing_capability": (
        "Camera Node software is too old for bounded clock calibration required by this "
        "acceptance run. Upgrade the Camera Node before continuing."
    ),
    "incompatible_protocol": (
        "Camera Node's health response did not match the protocol this Host expects. Confirm "
        "the Camera Node is running supported MockingBird Camera Node software, then try again."
    ),
    "calibration_failed": (
        "Camera Node advertises clock-calibration support, but a real calibration attempt did "
        "not succeed just now. Check network conditions between this Host and the Camera Node, "
        "then try again."
    ),
    "node_unreachable": (
        "Camera Node is not reachable on the network right now. Confirm it is powered on and "
        "connected, then try again."
    ),
    "camera_unavailable": (
        "The camera this Stream is configured to use is not currently available on the Camera "
        "Node. Check the camera connection on the Camera Node, then try again."
    ),
}


@dataclass(frozen=True)
class NodeCompatibilityResult:
    """One bounded compatibility verdict for one Stream's Camera Node, for
    one profile, at one point in time. JSON-serialization-friendly (every
    field is a primitive, a tuple of primitives, or `RttClockCalibrationRecord`
    -- already a plain frozen dataclass) so a caller can fold this directly
    into an existing structured report (Doctor, a field-acceptance script's
    own JSON output) without inventing a second envelope (Section 23)."""

    profile: CompatibilityProfile
    state: NodeCompatibilityState
    compatible: bool
    node_reachable: bool
    required_capabilities: tuple[str, ...]
    observed_capabilities: tuple[str, ...]
    missing_capabilities: tuple[str, ...]
    host_app_version: str
    host_git_commit: str | None
    node_api_version: str | None
    node_service_version: str | None
    camera_available: bool | None
    rtt_calibration: RttClockCalibrationRecord | None
    version_skew_detected: bool
    reasons: tuple[str, ...] = ()
    message: str = ""


def classify_node_compatibility(
    *,
    profile: CompatibilityProfile,
    reachable: bool,
    protocol_valid: bool,
    camera_checked: bool,
    camera_available: bool,
    rtt_fields_present: bool,
    rtt_calibration: RttClockCalibrationRecord | None,
) -> tuple[NodeCompatibilityState, tuple[str, ...], tuple[str, ...]]:
    """Pure decision table: given already-resolved facts (never live I/O --
    see `probe_node_compatibility` for that), return
    ``(state, reasons, missing_capabilities)``. `required_capabilities` for
    the profile is available separately from `REQUIRED_CAPABILITIES` --
    kept out of this return value since it depends only on `profile`, not
    on any observed fact.

    Ordering is deliberate and disclosed: an unreachable Node or a
    malformed/foreign protocol response is judged before any
    profile-specific capability, since neither can be meaningfully
    evaluated against the required-capability list at all. Within
    `field_acceptance`, a missing expected camera is judged before missing
    RTT capability when both are true -- the more fundamental, more
    immediately actionable problem (Section 12: tell an operator what to
    fix first)."""

    required = REQUIRED_CAPABILITIES[profile]

    if not reachable:
        return "node_unreachable", (_MESSAGES["node_unreachable"],), required
    if not protocol_valid:
        return "incompatible_protocol", (_MESSAGES["incompatible_protocol"],), required

    missing: list[str] = []
    if "expected_camera_available" in required and camera_checked and not camera_available:
        missing.append("expected_camera_available")
        return "camera_unavailable", (_MESSAGES["camera_unavailable"],), tuple(missing)

    if "rtt_timestamp_fields" in required and not rtt_fields_present:
        missing.append("rtt_timestamp_fields")
        return "incompatible_missing_capability", (_MESSAGES["incompatible_missing_capability"],), tuple(missing)

    if "bounded_rtt_clock_calibration" in required:
        calibrated = rtt_calibration is not None and rtt_calibration.state == "calibrated"
        if not calibrated:
            observed_state = rtt_calibration.state if rtt_calibration is not None else "not_attempted"
            missing.append("bounded_rtt_clock_calibration")
            return (
                "calibration_failed",
                (f"{_MESSAGES['calibration_failed']} (state: {observed_state})",),
                tuple(missing),
            )

    return "compatible", (), ()


def probe_node_compatibility(
    client: CameraNodeClient,
    *,
    stream_id: str,
    profile: CompatibilityProfile,
    base_address: str,
    credential: str | None = None,
    expected_camera_id: str | None = None,
    host_app_version: str,
    host_git_commit: str | None = None,
    rtt_batch_size: int = DEFAULT_FIELD_ACCEPTANCE_RTT_PROBE_BATCH_SIZE,
    clock: Callable[[], datetime] | None = None,
) -> NodeCompatibilityResult:
    """Live orchestration: fetch the Node's real health, optionally confirm
    the expected camera is live-available, and -- only for a profile that
    requires it, and only once the cheaper checks above already look
    satisfiable -- run one real bounded RTT-bounded calibration batch via
    the exact accepted `CameraNodeClient.sample_clock_round_trip`/
    `estimate_rtt_clock_calibration` functions (Section 20: never a second
    clock-calibration implementation). Synchronous and blocking, matching
    `CameraNodeClient`'s own convention (see `engine_runtime._perform_rtt_
    clock_calibration`'s `asyncio.to_thread` wrapping for how an async
    caller should invoke this).

    `credential`/`expected_camera_id` are optional: a caller with only a
    reachable `base_address` (an unauthenticated `/node/v1/health`
    call, exactly like `CameraNodeClient.health`/`sample_clock_round_trip`
    already require no credential) can still get a real reachability/RTT
    verdict without a paired credential -- `camera_available` on the result
    is `None` (not checked) rather than `False` (checked and absent) in
    that case. The `field_acceptance` enforcement path
    (`api/main.py:start_stream_observation`) always supplies both, since it
    only ever runs against an already-paired Stream."""

    clock = clock or (lambda: datetime.now(UTC))
    reachable = True
    health: Mapping[str, object] | None = None
    try:
        raw = client.health(base_address)
        health = raw if isinstance(raw, Mapping) else None
    except (CameraNodeClientError, OSError):
        reachable = False

    protocol_valid = reachable and health is not None and bool(health.get("node_id")) and bool(health.get("api_version"))
    node_api_version = health.get("api_version") if isinstance(health, Mapping) else None
    node_service_version = health.get("service_version") if isinstance(health, Mapping) else None
    rtt_fields_present = bool(
        protocol_valid
        and isinstance(health.get("node_receive_time"), str)
        and isinstance(health.get("node_time"), str)
    )

    camera_checked = protocol_valid and expected_camera_id is not None and credential is not None
    camera_available = False
    if camera_checked:
        try:
            cameras = client.cameras(base_address=base_address, credential=credential)
            camera_available = any(
                camera.camera_id == expected_camera_id and camera.status == "available" for camera in cameras
            )
        except (CameraNodeClientError, OSError):
            camera_available = False

    # Only spend a real bounded RTT batch once every cheaper prerequisite
    # already looks satisfiable -- an already-known-incompatible Node's
    # preflight stays cheap and fast (Section 26).
    need_rtt_probe = (
        profile == "field_acceptance"
        and protocol_valid
        and rtt_fields_present
        and (not camera_checked or camera_available)
    )
    rtt_calibration: RttClockCalibrationRecord | None = None
    if need_rtt_probe:
        samples: list[RttRoundTrip] = []
        for _ in range(rtt_batch_size):
            try:
                attempt = client.sample_clock_round_trip(base_address, clock=clock)
            except (CameraNodeClientError, OSError):
                continue
            samples.append(
                RttRoundTrip(
                    host_send_at=attempt.host_send_at,
                    host_receive_at=attempt.host_receive_at,
                    node_response_at=attempt.node_response_time,
                    node_receive_at=attempt.node_receive_time,
                )
            )
        rtt_calibration = estimate_rtt_clock_calibration(
            samples,
            stream_id=stream_id,
            # No one-way calibration baseline exists for a pre-session
            # preflight (there is no running session yet) -- `source_
            # offset_ms` is recorded on the resulting record purely for
            # cross-referencing against the one-way monitor elsewhere and
            # never affects the interval math itself (see `clock_
            # calibration.RttClockCalibrationRecord`'s own docstring).
            source_offset_ms=0,
            calibrated_at=clock(),
        )

    state, reasons, missing_capabilities = classify_node_compatibility(
        profile=profile,
        reachable=reachable,
        protocol_valid=protocol_valid,
        camera_checked=camera_checked,
        camera_available=camera_available,
        rtt_fields_present=rtt_fields_present,
        rtt_calibration=rtt_calibration,
    )
    required_capabilities = REQUIRED_CAPABILITIES[profile]
    observed_capabilities = tuple(c for c in required_capabilities if c not in missing_capabilities)

    # Genuinely comparable only when both sides report the *same* kind of
    # identity string -- today that is never true (the Camera Node has
    # never exposed a live `git_commit`; `service_version`/`host_app_
    # version` are both a static package version, currently "0.1.0" on
    # both sides, see the milestone report's own "Version-skew behavior"
    # for the honest disclosure that this signal is real but currently
    # weak). Never used to fail compatibility either way (Section 24).
    version_skew_detected = bool(
        node_service_version and host_app_version and node_service_version != host_app_version
    )

    return NodeCompatibilityResult(
        profile=profile,
        state=state,
        compatible=state == "compatible",
        node_reachable=reachable,
        required_capabilities=required_capabilities,
        observed_capabilities=observed_capabilities,
        missing_capabilities=missing_capabilities,
        host_app_version=host_app_version,
        host_git_commit=host_git_commit,
        node_api_version=node_api_version if isinstance(node_api_version, str) else None,
        node_service_version=node_service_version if isinstance(node_service_version, str) else None,
        camera_available=(camera_available if camera_checked else None),
        rtt_calibration=rtt_calibration,
        version_skew_detected=version_skew_detected,
        reasons=reasons,
        message=_MESSAGES[state],
    )
