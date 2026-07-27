"""In-process bounded snapshot bridge for a paired MockingBird Camera Node.

It presents frames through the existing live-session pipe boundary so Zones,
motion evaluation, and evidence handoff remain shared product behavior. It is
not a Node recorder and never writes a preview frame to disk.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

from mockingbird.source_providers.camera_node import CameraNodeClient, CameraNodeClientError


SNAPSHOT_INTERVAL_SECONDS = 1.0
PROFILE_LOOKUP_ATTEMPTS = 12
PROFILE_LOOKUP_RETRY_DELAY_SECONDS = 0.25


class CameraNodeSnapshotProcess:
    """Small Popen-shaped frame producer used only by ``LiveCameraSessionManager``."""

    def __init__(self, config: Any, *, client: CameraNodeClient | None = None) -> None:
        self._config = config
        self._client = client or CameraNodeClient()
        read_fd, self._write_fd = os.pipe()
        self.stdout = os.fdopen(read_fd, "rb", buffering=0)
        self._stopped = threading.Event()
        self._return_code: int | None = None
        self.safe_failure_code: str | None = None
        self._monitoring_profile = None
        self._thread = threading.Thread(
            target=self._run,
            name=f"mockingbird-camera-node-{config.stream_id}",
            daemon=True,
        )
        self._thread.start()

    def poll(self) -> int | None:
        return self._return_code

    def terminate(self) -> None:
        self._stopped.set()
        self._close_writer(0)

    def kill(self) -> None:
        self.terminate()

    def wait(self, timeout: float | None = None) -> int:
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            raise TimeoutError("camera_node_bridge_stop_timeout")
        return self._return_code or 0

    def _monitoring_profile_from_capabilities(
        self, profile_id: str
    ) -> tuple[Any | None, bool]:
        """Wait only through a bounded warm-up window for the durable opaque ID."""

        camera_id = self._config.camera_node_camera_id or ""
        still_warming = False
        for attempt in range(PROFILE_LOOKUP_ATTEMPTS):
            cameras = self._client.cameras(
                base_address=self._config.camera_node_base_address or "",
                credential=self._config.camera_node_credential or "",
            )
            camera = next(
                (item for item in cameras if item.camera_id == camera_id), None
            )
            profile = next(
                (
                    item
                    for item in (camera.capture_profiles if camera else ())
                    if item.profile_id == profile_id and item.supports_monitoring
                ),
                None,
            )
            if profile is not None:
                return profile, False
            still_warming = bool(
                camera is not None
                and camera.capture_readiness in {"not_initialized", "warming"}
            )
            if (
                not still_warming
                or attempt == PROFILE_LOOKUP_ATTEMPTS - 1
                or self._stopped.wait(PROFILE_LOOKUP_RETRY_DELAY_SECONDS)
            ):
                break
        return None, still_warming

    def _run(self) -> None:
        try:
            profile_id = getattr(
                self._config, "camera_node_monitoring_profile_id", None
            )
            if profile_id:
                try:
                    self._monitoring_profile, still_warming = (
                        self._monitoring_profile_from_capabilities(profile_id)
                    )
                except CameraNodeClientError as error:
                    self.safe_failure_code = str(error)
                    return
                if self._monitoring_profile is None:
                    self.safe_failure_code = (
                        "provider_warming"
                        if still_warming
                        else "node_capture_profile_unavailable"
                    )
                    return
            while not self._stopped.is_set():
                try:
                    if self._monitoring_profile is None:
                        frame = self._client.snapshot(
                            base_address=self._config.camera_node_base_address or "",
                            credential=self._config.camera_node_credential or "",
                            camera_id=self._config.camera_node_camera_id or "",
                        )
                    else:
                        frame = self._client.capture(
                            base_address=self._config.camera_node_base_address or "",
                            credential=self._config.camera_node_credential or "",
                            camera_id=self._config.camera_node_camera_id or "",
                            profile=self._monitoring_profile,
                        ).image
                except CameraNodeClientError as error:
                    # The main app records only these product-safe codes, never transport text.
                    self.safe_failure_code = str(error)
                    # Let the durable supervisor own bounded restart/backoff rather
                    # than leaving an unreachable or rejected Node in a tight
                    # background retry loop.
                    break
                try:
                    os.write(self._write_fd, frame)
                except BrokenPipeError:
                    break
                if self._stopped.wait(SNAPSHOT_INTERVAL_SECONDS):
                    break
        finally:
            self._close_writer(0 if self._stopped.is_set() else 1)

    def _close_writer(self, code: int) -> None:
        if self._return_code is not None:
            return
        self._return_code = code
        try:
            os.close(self._write_fd)
        except OSError:
            pass
