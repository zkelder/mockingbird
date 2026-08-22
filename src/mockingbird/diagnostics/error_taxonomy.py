"""A shared, stable, structured-error shape spanning MockingBird's components.

Confirmed by direct code archaeology (see `doctor.DoctorCheckCode`'s own
docstring) that no such shared taxonomy existed before this module: every
subsystem defines its own bare ``XxxError(ValueError)`` with a free-form
string "code," decoded only via ``str(error)`` at whatever API boundary
happens to catch it. This module does not replace any of those exception
classes or their already-correct user-facing text -- rewriting ~20
independent, already-tested error hierarchies would be a large, risky
change for no behavioral gain. Instead it gives the highest-value existing
codes one shared, additive *shape* (`StructuredError`) they can be reported
through at an API boundary or a structured log line, plus a small, honestly
incomplete registry (`ERROR_TAXONOMY`) that reuses each code's existing
user-facing text verbatim rather than inventing new copy. A code with no
registry entry still gets a safe, honest, non-leaking default -- the
registry is additive, never a hard requirement to add a new error.

Deliberately dependency-light: this module is imported from request-path
code (`api.main`), so it must not pull in the Observation Engine/BioCLIP/
ONNX import graph the way `mockingbird.diagnostics.doctor` legitimately
does for its own bounded, CLI-only checks.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ErrorComponent(str, Enum):
    """The ten component groups this taxonomy spans (see the milestone's
    "Stable structured error taxonomy" scope)."""

    HOST_API = "host_api"
    CAMERA_NODE = "camera_node"
    ACQUISITION_PROVIDER = "acquisition_provider"
    OBSERVATION_ENGINE = "observation_engine"
    MODEL_RUNTIME = "model_runtime"
    DATABASE = "database"
    MEDIA_STORAGE = "media_storage"
    OFFLINE_INGEST = "offline_ingest"
    EXPORT_RESEARCH = "export_research"
    FRONTEND = "frontend"


class ErrorRecoverability(str, Enum):
    """Reuses Doctor's own severity vocabulary rather than inventing a
    second one -- see "Severity semantics" in
    docs/mockingbird-doctor-operational-health-contract.md. `BLOCKING` is
    reserved for a failure that means the core loop cannot proceed at all
    (a database write failure, a storage-full condition); most acquisition/
    provider/model failures are `DEGRADED` (a real problem, reduced
    capability, the rest of the product still works); `INFORMATIONAL` is
    for an honest non-error state reported through this same shape (for
    example, an optional capability that was never configured)."""

    BLOCKING = "blocking"
    DEGRADED = "degraded"
    INFORMATIONAL = "informational"


class ErrorCorrelation(BaseModel):
    """Bounded identifiers for tracing one failure through the pipeline
    (Camera Node/provider request -> host acquisition -> Observation Engine
    session -> proposal/Visit creation -> evidence persistence -> API/UI
    result). Every field is optional; a caller supplies only the
    identifiers it actually has for this failure -- never all seven merely
    because the shape allows it (see "Do not make every log line carry all
    IDs" in the milestone brief)."""

    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    correlation_id: str | None = None
    observation_session_id: str | None = None
    source_id: str | None = None
    stream_id: str | None = None
    event_id: str | None = None
    visit_id: str | None = None

    def is_empty(self) -> bool:
        return not any(
            (
                self.request_id,
                self.correlation_id,
                self.observation_session_id,
                self.source_id,
                self.stream_id,
                self.event_id,
                self.visit_id,
            )
        )


class StructuredError(BaseModel):
    """One stable, machine-readable error record.

    This is the shape a caught exception's existing bare-string code gets
    reported through at an API boundary or a structured log line --
    never a replacement for the exception itself. `message` is always
    user-safe (no stack trace, no filesystem path, no credential -- see
    `bounded_exception_detail` for where raw exception text is allowed to
    go instead). `diagnostic` mirrors Doctor's own `diagnostic_context`
    convention: a bounded dict, advanced/JSON-only, never the primary
    message.
    """

    code: str
    component: ErrorComponent
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str
    recoverability: ErrorRecoverability
    retryable: bool = False
    correlation: ErrorCorrelation = Field(default_factory=ErrorCorrelation)
    diagnostic: dict[str, Any] | None = None


class ErrorTaxonomyEntry(BaseModel):
    """One registered code's stable, reusable presentation."""

    component: ErrorComponent
    message: str
    recoverability: ErrorRecoverability
    retryable: bool = False
    user_action: str | None = None


def bounded_exception_detail(error: BaseException, *, max_length: int = 200) -> str:
    """A short, advanced-diagnostics-only exception summary.

    Never used for a `StructuredError.message` (the always-shown field) --
    a raw Python exception must never be the normal user-facing message.
    Mirrors `diagnostics.doctor._bounded_exception_detail`'s exact
    contract; kept as an independent, dependency-light copy here rather
    than importing from `doctor.py`, which pulls in the heavy Observation
    Engine/BioCLIP/ONNX import graph this widely-imported, request-path
    module must not carry.
    """

    text = f"{type(error).__name__}: {error}"
    return text if len(text) <= max_length else text[: max_length - 1] + "…"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
#
# Deliberately incomplete: this seeds the highest-value codes already in
# active use across every component group, reusing each one's existing
# user-facing text verbatim (cited in the comment above each block) rather
# than inventing new copy. Adding a new component's codes here as they are
# touched is expected and welcome; this is not a big-bang rewrite of every
# `XxxError` in the codebase (see the module docstring).

ERROR_TAXONOMY: dict[str, ErrorTaxonomyEntry] = {}


def _register(code: str, entry: ErrorTaxonomyEntry) -> None:
    ERROR_TAXONOMY[code] = entry


# -- CAMERA_NODE: reuses api.main._camera_node_pairing_http_error's text --
for _code, _message, _user_action, _retryable in (
    (
        "node_address_invalid",
        "Enter a complete HTTP or HTTPS Camera Node address.",
        "Check the Camera Node's address and try again.",
        False,
    ),
    (
        "node_address_requires_lan_ip",
        "Use an explicit local LAN IP address; discovery names are not supported yet.",
        "Enter the Camera Node's LAN IP address directly.",
        False,
    ),
    (
        "node_address_not_local",
        "Camera Node addresses must be local LAN addresses.",
        "Enter a local network address for the Camera Node.",
        False,
    ),
    (
        "pairing_code_malformed",
        "Enter the Camera Node's one-time pairing code.",
        "Re-enter the pairing code shown on the Camera Node.",
        False,
    ),
    (
        "pairing_code_expired",
        "The Camera Node pairing code expired.",
        "Start the Node again for a new code.",
        True,
    ),
    (
        "pairing_rate_limited",
        "Pairing attempts are temporarily limited on the Camera Node.",
        "Wait a moment, then try pairing again.",
        True,
    ),
    (
        "pairing_rejected",
        "The Camera Node pairing code was rejected.",
        "Check the pairing code and try again.",
        True,
    ),
    (
        "node_api_unsupported",
        "This Camera Node uses an unsupported API version.",
        "Update the Camera Node software to a supported version.",
        False,
    ),
    (
        "node_unavailable",
        "Camera Node is unavailable. Check the local Node before completing setup.",
        "Check the Camera Node's power and network connection, then try again.",
        True,
    ),
    (
        "authentication_rejected",
        "Camera Node pairing is no longer accepted.",
        "Pair the Camera Node again.",
        False,
    ),
):
    _register(
        _code,
        ErrorTaxonomyEntry(
            component=ErrorComponent.CAMERA_NODE,
            message=_message,
            recoverability=ErrorRecoverability.DEGRADED,
            retryable=_retryable,
            user_action=_user_action,
        ),
    )

# -- ACQUISITION_PROVIDER: reuses api.main._ONVIF_DISCOVERY_ERROR_MESSAGES
#    and the RTSPS refusal text already written for playback status
#    (product_repository.py) / session start (api.main) --
for _code, _message, _user_action in (
    (
        "onvif_unreachable",
        "Could not connect to this camera. Check the host and port.",
        "Check the camera's network address and that it is powered on.",
    ),
    (
        "onvif_authentication_rejected",
        "The camera rejected this username/password.",
        "Check the camera username/password.",
    ),
    (
        "onvif_no_profiles",
        "This camera has no media profiles to choose from.",
        "Check the camera's own ONVIF/media configuration.",
    ),
    (
        "camera_setup_invalid_url",
        "Enter a valid URL for the selected provider.",
        "Check the camera's URL for typos.",
    ),
    (
        "camera_setup_rtsps_unsupported",
        (
            "RTSPS (secure RTSP) is not currently supported. MockingBird cannot verify a "
            "TLS-secured connection to this camera. Use rtsp:// on a trusted local network "
            "instead."
        ),
        "Change the camera's URL to use rtsp:// instead of rtsps://.",
    ),
    (
        "camera_node_legacy_monitoring_unsupported",
        (
            "Camera Node streams use the Observation Engine, not legacy durable monitoring. "
            "Finish setup with monitoring off, then use Start observing afterward."
        ),
        "Finish setup, then use Start observing from this camera's page.",
    ),
):
    _register(
        _code,
        ErrorTaxonomyEntry(
            component=ErrorComponent.ACQUISITION_PROVIDER,
            message=_message,
            recoverability=ErrorRecoverability.DEGRADED,
            retryable=_code in {"onvif_unreachable", "node_unavailable"},
            user_action=_user_action,
        ),
    )

# -- ACQUISITION_PROVIDER: Pre-Freeze Operability Gap Closure v1 ("Live RTSP
#    Setup Validation" -- see rtsp_bridge.probe_rtsp_stream). Manual RTSP
#    setup must not claim a source is ready merely because its URL is
#    syntactically valid; these are the bounded, distinguishable outcomes a
#    real live probe can honestly report. New codes -- no prior structured
#    text existed for any of these (setup validation previously never
#    attempted a live connection at all). --
for _code, _message, _user_action, _retryable in (
    (
        "camera_setup_rtsp_unreachable",
        "Could not reach this camera's RTSP stream. Check the URL, network, and that the camera is powered on.",
        "Check the camera's network address and that it is powered on, then try again.",
        True,
    ),
    (
        "camera_setup_rtsp_authentication_failed",
        "The camera rejected this stream's username/password.",
        "Check the RTSP URL's username and password.",
        False,
    ),
    (
        "camera_setup_rtsp_negotiation_failed",
        "MockingBird connected but this camera did not negotiate a usable RTSP stream at this URL.",
        "Check the RTSP path in the URL against the camera's own documentation.",
        True,
    ),
    (
        "camera_setup_rtsp_unsupported_codec",
        "This stream's video codec is not supported for analysis.",
        "Set the camera's stream to a widely-supported codec (e.g. H.264) and try again.",
        False,
    ),
    (
        "camera_setup_rtsp_decode_failed",
        "MockingBird connected but could not decode a usable video frame from this stream.",
        "Check the camera's stream settings and try again.",
        True,
    ),
    (
        "camera_setup_rtsp_validation_timed_out",
        "Validating this RTSP stream took too long and was stopped.",
        "Check the camera's network connection and try again.",
        True,
    ),
    (
        "camera_setup_rtsp_ffmpeg_unavailable",
        "Video decoding is unavailable on this installation.",
        "Reinstalling MockingBird usually fixes this.",
        False,
    ),
):
    _register(
        _code,
        ErrorTaxonomyEntry(
            component=ErrorComponent.ACQUISITION_PROVIDER,
            message=_message,
            recoverability=ErrorRecoverability.DEGRADED,
            retryable=_retryable,
            user_action=_user_action,
        ),
    )

# -- OBSERVATION_ENGINE: reuses observation.engine_runtime._engine_failure_message's
#    two named categories --
_register(
    "missing_model_or_runtime",
    ErrorTaxonomyEntry(
        component=ErrorComponent.OBSERVATION_ENGINE,
        message="The Observation Engine's model bundle is missing or invalid.",
        recoverability=ErrorRecoverability.DEGRADED,
        user_action="Reinstalling MockingBird usually fixes this.",
    ),
)
_register(
    "unsupported_gpu",
    ErrorTaxonomyEntry(
        component=ErrorComponent.OBSERVATION_ENGINE,
        message=(
            "This PC's GPU/graphics driver does not meet Observation Engine requirements "
            "(a compatible NVIDIA GPU and driver are required)."
        ),
        recoverability=ErrorRecoverability.DEGRADED,
        user_action="Verify a compatible NVIDIA GPU, driver, and CUDA runtime are installed.",
    ),
)

# -- MODEL_RUNTIME: reuses repository.product_repository._BIOCLIP_ATTEMPT_ERROR_FIELDS'
#    existing detail text --
for _code, _message in (
    ("bioclip_busy", "Another manual species-identification run already owns the local runtime."),
    ("bioclip_timed_out", "Species identification took too long and was stopped."),
    ("bioclip_configuration_error", "The local species-identification configuration was not usable."),
    ("bioclip_not_configured", "Species identification is not configured on this installation."),
):
    _register(
        _code,
        ErrorTaxonomyEntry(
            component=ErrorComponent.MODEL_RUNTIME,
            message=_message,
            recoverability=(
                ErrorRecoverability.INFORMATIONAL if _code == "bioclip_not_configured" else ErrorRecoverability.DEGRADED
            ),
            retryable=_code in {"bioclip_busy", "bioclip_timed_out"},
            user_action=(
                "Check the configured BioCLIP model/labels files, or see "
                "docs/species-suggestion-adapter-design.md."
                if _code in {"bioclip_configuration_error", "bioclip_not_configured"}
                else "Try again."
            ),
        ),
    )

# -- DATABASE: new -- see "Structured logging" B4/B2 in the milestone brief;
#    no prior code existed for a raw DB write failure at all. --
_register(
    "storage_write_failed",
    ErrorTaxonomyEntry(
        component=ErrorComponent.DATABASE,
        message="MockingBird could not save this change. Try again, or check available storage.",
        recoverability=ErrorRecoverability.DEGRADED,
        retryable=True,
        user_action="Try again. If this keeps happening, check available disk space (MockingBird Doctor).",
    ),
)

# -- MEDIA_STORAGE: reuses diagnostics.doctor's own Storage check text --
_register(
    "storage_low_space",
    ErrorTaxonomyEntry(
        component=ErrorComponent.MEDIA_STORAGE,
        message="Free disk space is low.",
        recoverability=ErrorRecoverability.DEGRADED,
        user_action="Free up disk space, or move MockingBird's data folder to a drive with more room.",
    ),
)
_register(
    "storage_not_writable",
    ErrorTaxonomyEntry(
        component=ErrorComponent.MEDIA_STORAGE,
        message="The storage folder is not writable.",
        recoverability=ErrorRecoverability.BLOCKING,
        user_action="Check folder permissions for the configured MockingBird data folder.",
    ),
)

# -- OFFLINE_INGEST: reuses observation.offline_ingest._decode_error_message's
#    existing text --
for _code, _message in (
    ("media_file_invalid", "This recorded file could not be read as a video."),
    ("unsupported_codec", "This video's codec is not supported for analysis."),
    ("decode_failed", "This video could not be decoded."),
    ("ffmpeg_unavailable", "Video decoding is unavailable on this installation."),
):
    _register(
        _code,
        ErrorTaxonomyEntry(
            component=ErrorComponent.OFFLINE_INGEST,
            message=_message,
            recoverability=ErrorRecoverability.DEGRADED,
            user_action=(
                "Convert the file to a widely-supported codec (e.g. H.264) and try again."
                if _code == "unsupported_codec"
                else "Check the file and try again."
            ),
        ),
    )

# -- EXPORT_RESEARCH: new stable code replacing one non-conforming
#    full-sentence ValueError message found during this milestone's
#    observability inventory (repository.product_repository's Camtrap DP
#    export path used to raise the literal sentence itself). --
_register(
    "camtrap_dp_export_directory_exists",
    ErrorTaxonomyEntry(
        component=ErrorComponent.EXPORT_RESEARCH,
        message="A Camtrap DP export with this identifier already exists.",
        recoverability=ErrorRecoverability.DEGRADED,
        user_action="Choose a different export identifier, or remove the existing export folder first.",
    ),
)

# -- HOST_API: a safe, honest fallback for a code this registry has no
#    specific entry for yet (see `resolve_error`). --
_register(
    "internal_error",
    ErrorTaxonomyEntry(
        component=ErrorComponent.HOST_API,
        message="MockingBird ran into a problem completing this action.",
        recoverability=ErrorRecoverability.DEGRADED,
        retryable=True,
        user_action="Try again. If this keeps happening, check MockingBird Doctor for more detail.",
    ),
)


def resolve_error(
    code: str,
    *,
    default_component: ErrorComponent = ErrorComponent.HOST_API,
    default_message: str | None = None,
) -> ErrorTaxonomyEntry:
    """Look up a known code; fall back to a safe, honest default for an
    unregistered code rather than raising. The registry is additive and
    deliberately incomplete (see module docstring) -- every component must
    still get a safe, non-leaking response even for a code nobody has
    registered specific text for yet."""

    entry = ERROR_TAXONOMY.get(code)
    if entry is not None:
        return entry
    return ErrorTaxonomyEntry(
        component=default_component,
        message=default_message or ERROR_TAXONOMY["internal_error"].message,
        recoverability=ErrorRecoverability.DEGRADED,
        retryable=False,
    )


def build_structured_error(
    code: str,
    *,
    default_component: ErrorComponent = ErrorComponent.HOST_API,
    correlation: ErrorCorrelation | None = None,
    diagnostic: dict[str, Any] | None = None,
    message_override: str | None = None,
) -> StructuredError:
    """Build one `StructuredError` for a caught exception's code, reusing a
    registered entry's component/message/recoverability/retryable when one
    exists. `diagnostic` is the only place raw exception detail may ever
    go -- see `bounded_exception_detail`."""

    entry = resolve_error(code, default_component=default_component)
    return StructuredError(
        code=code,
        component=entry.component,
        message=message_override or entry.message,
        recoverability=entry.recoverability,
        retryable=entry.retryable,
        correlation=correlation or ErrorCorrelation(),
        diagnostic=diagnostic,
    )
