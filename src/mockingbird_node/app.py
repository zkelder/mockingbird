"""Authenticated, local-only HTTP surface for a MockingBird Camera Node."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import secrets
import threading

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from .config import CameraNodeConfig
from .providers import (
    CameraProvider,
    NodeCamera,
    NodeCaptureProfile,
    NodeCaptureResult,
    create_camera_provider,
)


NODE_API_VERSION = "v1"
_MAX_PAIR_ATTEMPTS = 5
_RECOMMENDED_SNAPSHOT_TIMEOUT_SECONDS = 8.0


class PairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pairing_code: str = Field(min_length=8, max_length=128)


class PairResponse(BaseModel):
    node_id: str
    display_name: str
    api_version: str
    credential: str
    cameras: list[dict[str, object]]


class CaptureRequest(BaseModel):
    """An opaque, pre-advertised profile is the only capture control."""

    model_config = ConfigDict(extra="forbid")
    profile_id: str = Field(min_length=1, max_length=120)


class _PairingState:
    def __init__(self, ttl_seconds: int) -> None:
        self._code = secrets.token_urlsafe(18)
        self._expires_at = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        self._credential: str | None = None
        self._attempts = 0
        self._revoked: set[str] = set()
        self._lock = threading.RLock()

    @property
    def code(self) -> str:
        return self._code

    @property
    def expires_at(self) -> datetime:
        return self._expires_at

    def pair(self, code: str) -> str:
        with self._lock:
            if datetime.now(UTC) >= self._expires_at:
                raise ValueError("pairing_code_expired")
            if self._credential is not None:
                raise ValueError("pairing_code_used")
            if self._attempts >= _MAX_PAIR_ATTEMPTS:
                raise ValueError("pairing_rate_limited")
            if not hmac.compare_digest(code, self._code):
                self._attempts += 1
                raise ValueError("pairing_rejected")
            self._credential = secrets.token_urlsafe(32)
            return self._credential

    def authenticated(self, credential: str) -> bool:
        with self._lock:
            return bool(self._credential and credential not in self._revoked and hmac.compare_digest(credential, self._credential))

    def revoke(self, credential: str) -> bool:
        with self._lock:
            if not self.authenticated(credential):
                return False
            self._revoked.add(credential)
            return True


def _camera_payload(
    camera: NodeCamera,
    *,
    profiles: list[NodeCaptureProfile] | None = None,
    capture_readiness: str = "not_initialized",
    capture_profile_status: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return {
        "camera_id": camera.camera_id,
        "display_name": camera.display_name,
        "status": camera.status,
        "setup_hint": camera.setup_hint,
        "snapshot_supported": camera.snapshot_supported,
        "provider_type": camera.provider_type,
        "capture_profiles": [profile.as_payload() for profile in (profiles or [])],
        "capture_readiness": capture_readiness,
        "capture_profile_status": capture_profile_status or [],
    }


def _provider_capture_profiles(
    provider: CameraProvider,
    camera_id: str,
) -> list[NodeCaptureProfile]:
    """Old v1 Nodes remain snapshot-compatible when they expose no profiles."""

    method = getattr(provider, "capture_profiles", None)
    if not callable(method):
        return []
    profiles = method(camera_id)
    return [item for item in profiles if isinstance(item, NodeCaptureProfile)]


def _provider_capture_profile_status(
    provider: CameraProvider,
    camera_id: str,
) -> list[dict[str, str]]:
    """Pass through only the small fixed diagnostic vocabulary old Nodes omit."""

    method = getattr(provider, "capture_profile_status", None)
    if not callable(method):
        return []
    raw_status = method(camera_id)
    if not isinstance(raw_status, list):
        return []
    allowed_states = {
        "untested",
        "testing",
        "accepted",
        "rejected_resource",
        "rejected_alignment",
        "rejected_latency",
        "rejected_capture",
        "rejected_configuration",
    }
    status: list[dict[str, str]] = []
    for item in raw_status[:12]:
        if not isinstance(item, dict):
            continue
        profile_id, state = item.get("profile_id"), item.get("state")
        if (
            isinstance(profile_id, str)
            and 0 < len(profile_id) <= 120
            and "/" not in profile_id
            and isinstance(state, str)
            and state in allowed_states
        ):
            status.append({"profile_id": profile_id, "state": state})
    return status


def _jpeg_dimensions(data: bytes) -> tuple[int, int] | None:
    """Read JPEG dimensions without decoding an untrusted image."""
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


def create_node_app(config: CameraNodeConfig | None = None, *, provider: CameraProvider | None = None) -> FastAPI:
    config = config or CameraNodeConfig.from_environment()
    provider = provider or create_camera_provider(config)
    pairing = _PairingState(config.pairing_ttl_seconds)
    node_id = f"node-{hashlib.sha256(config.display_name.encode()).hexdigest()[:16]}"
    app = FastAPI(title="MockingBird Camera Node", version=NODE_API_VERSION)

    def camera_payload(camera: NodeCamera) -> dict[str, object]:
        profiles = _provider_capture_profiles(provider, camera.camera_id)
        readiness = getattr(provider, "capture_readiness", lambda _camera_id: "not_initialized")(camera.camera_id)
        return _camera_payload(
            camera,
            profiles=profiles,
            capture_readiness=readiness if readiness in {"not_initialized", "warming", "ready", "degraded", "unavailable"} else "unavailable",
            capture_profile_status=_provider_capture_profile_status(
                provider, camera.camera_id
            ),
        )

    def capture_response(camera_id: str, profile_id: str) -> Response:
        camera = {item.camera_id: item for item in provider.cameras()}.get(camera_id)
        if camera is None:
            raise HTTPException(status_code=404, detail="Camera is unavailable.")
        if camera.status != "available" or not camera.snapshot_supported:
            raise HTTPException(status_code=409, detail="Camera setup is required.")
        profiles = {
            item.profile_id: item
            for item in _provider_capture_profiles(provider, camera_id)
        }
        profile = profiles.get(profile_id)
        if profile is None or not profile.jpeg_supported:
            raise HTTPException(status_code=409, detail="Camera capture profile is unavailable.")
        try:
            result = provider.snapshot(camera_id, profile_id=profile.profile_id)
        except ValueError as error:
            error_code, status, detail = {
                "camera_busy": ("node_camera_unavailable", 409, "Camera is busy."),
                "camera_permission_denied": ("node_camera_unavailable", 403, "Camera permission is required on this Node."),
                "camera_setup_required": ("node_camera_unavailable", 409, "Camera setup is required."),
                "camera_warmup_timeout": ("node_camera_warmup_timeout", 503, "Camera warm-up timed out."),
                "camera_capture_timeout": ("node_snapshot_timeout", 503, "Camera snapshot timed out."),
                "camera_unusable_frame": ("node_snapshot_invalid", 503, "Camera did not provide a usable image."),
                "capture_profile_not_allowed": ("node_capture_profile_unavailable", 409, "Camera capture profile is unavailable."),
                "provider_reset_required": ("provider_reset_required", 503, "Camera provider needs a reset."),
            }.get(str(error), ("node_camera_unavailable", 409, "Camera is unavailable."))
            raise HTTPException(
                status_code=status,
                detail=detail,
                headers={"X-MockingBird-Node-Error": error_code},
            ) from None
        if isinstance(result, NodeCaptureResult):
            image = result.image
            monitoring_recovery = result.monitoring_recovery
        else:
            # Existing providers return raw bytes. Keep that provider contract
            # compatible while profile-aware providers add safe recovery state.
            image = result
            monitoring_recovery = None
        dimensions = _jpeg_dimensions(image)
        if (
            not dimensions
            or len(image) > profile.max_expected_bytes
            or dimensions[0] > profile.width
            or dimensions[1] > profile.height
        ):
            raise HTTPException(
                status_code=503,
                detail="Camera frame is outside the selected profile bounds.",
                headers={"X-MockingBird-Node-Error": "node_snapshot_invalid"},
            )
        captured_at = datetime.now(UTC).isoformat()
        headers = {
            "Cache-Control": "no-store",
            "X-MockingBird-Frame-At": captured_at,
            "X-MockingBird-Captured-At": captured_at,
            "X-MockingBird-Capture-Profile": profile.profile_id,
        }
        if monitoring_recovery in {"restored", "reset_required"}:
            headers["X-MockingBird-Monitoring-Recovery"] = monitoring_recovery
        return Response(
            content=image,
            media_type="image/jpeg",
            headers=headers,
        )

    def require_pairing(request: Request) -> str:
        prefix, _, credential = request.headers.get("authorization", "").partition(" ")
        if prefix.lower() != "bearer" or not credential or not pairing.authenticated(credential):
            raise HTTPException(status_code=401, detail="Pairing authentication is required.")
        return credential

    @app.get("/node/v1/health")
    def health() -> dict[str, object]:
        cameras = provider.cameras()
        return {"node_id": node_id, "display_name": config.display_name, "api_version": NODE_API_VERSION, "status": "available", "camera_count": len(cameras), "available_camera_count": sum(camera.status == "available" for camera in cameras), "pairing_required": True}

    @app.post("/node/v1/pair", response_model=PairResponse)
    def pair(payload: PairRequest) -> PairResponse:
        try:
            credential = pairing.pair(payload.pairing_code)
        except ValueError as error:
            status, detail = {"pairing_code_expired": (410, "Pairing code expired."), "pairing_code_used": (409, "Pairing code was already used."), "pairing_rate_limited": (429, "Pairing attempts are temporarily limited.")}.get(str(error), (401, "Pairing code was rejected."))
            raise HTTPException(status_code=status, detail=detail) from None
        return PairResponse(node_id=node_id, display_name=config.display_name, api_version=NODE_API_VERSION, credential=credential, cameras=[camera_payload(camera) for camera in provider.cameras()])

    @app.get("/node/v1/capabilities")
    def capabilities(_: str = Depends(require_pairing)) -> dict[str, object]:
        return {
            "node_id": node_id,
            "api_version": NODE_API_VERSION,
            "snapshot_supported": True,
            "preview_mjpeg_supported": False,
            "capture_profiles_supported": True,
            "max_image_bytes": config.max_image_bytes,
            "max_image_width": config.max_image_width,
            "max_image_height": config.max_image_height,
            "max_evidence_image_bytes": config.effective_evidence_max_image_bytes,
            "max_evidence_image_width": config.effective_evidence_max_image_width,
            "max_evidence_image_height": config.effective_evidence_max_image_height,
            "max_preview_viewers": config.max_preview_viewers,
            # Optional v1 metadata: the desktop clamps this to its own hard limit.
            "recommended_snapshot_timeout_seconds": _RECOMMENDED_SNAPSHOT_TIMEOUT_SECONDS,
        }

    @app.get("/node/v1/cameras")
    def cameras(_: str = Depends(require_pairing)) -> dict[str, object]:
        return {"items": [camera_payload(camera) for camera in provider.cameras()]}

    @app.get("/node/v1/cameras/{camera_id}/snapshot")
    def snapshot(camera_id: str, _: str = Depends(require_pairing)) -> Response:
        camera = {item.camera_id: item for item in provider.cameras()}.get(camera_id)
        if camera is None:
            raise HTTPException(status_code=404, detail="Camera is unavailable.")
        if camera.status != "available" or not camera.snapshot_supported:
            raise HTTPException(status_code=409, detail="Camera setup is required.")
        try:
            result = provider.snapshot(camera_id)
        except ValueError as error:
            error_code, status, detail = {
                "camera_busy": ("node_camera_unavailable", 409, "Camera is busy."),
                "camera_permission_denied": ("node_camera_unavailable", 403, "Camera permission is required on this Node."),
                "camera_setup_required": ("node_camera_unavailable", 409, "Camera setup is required."),
                "camera_warmup_timeout": ("node_camera_warmup_timeout", 503, "Camera warm-up timed out."),
                "camera_capture_timeout": ("node_snapshot_timeout", 503, "Camera snapshot timed out."),
                "camera_unusable_frame": ("node_snapshot_invalid", 503, "Camera did not provide a usable image."),
                "provider_reset_required": ("provider_reset_required", 503, "Camera provider needs a reset."),
            }.get(str(error), ("node_camera_unavailable", 409, "Camera is unavailable."))
            raise HTTPException(
                status_code=status,
                detail=detail,
                headers={"X-MockingBird-Node-Error": error_code},
            ) from None
        image = result.image if isinstance(result, NodeCaptureResult) else result
        dimensions = _jpeg_dimensions(image)
        if not dimensions or len(image) > config.max_image_bytes or dimensions[0] > config.max_image_width or dimensions[1] > config.max_image_height:
            raise HTTPException(status_code=503, detail="Camera frame is outside Node bounds.")
        return Response(content=image, media_type="image/jpeg", headers={"Cache-Control": "no-store", "X-MockingBird-Frame-At": datetime.now(UTC).isoformat()})

    @app.post("/node/v1/cameras/{camera_id}/capture")
    def capture(
        camera_id: str,
        payload: CaptureRequest,
        _: str = Depends(require_pairing),
    ) -> Response:
        return capture_response(camera_id, payload.profile_id)

    @app.post("/node/v1/pair/revoke", status_code=204)
    def revoke(credential: str = Depends(require_pairing)) -> Response:
        pairing.revoke(credential)
        return Response(status_code=204)

    @app.on_event("shutdown")
    def shutdown_provider() -> None:
        provider.close()

    app.state.pairing_code = pairing.code  # local launcher display/test only, never an HTTP response
    app.state.pairing_expires_at = pairing.expires_at
    return app
