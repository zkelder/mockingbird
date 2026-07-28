"""Shared, bounded facts for durable healthy monitoring exposure."""

from __future__ import annotations

from datetime import timedelta


# This is deliberately coarser than frame delivery: exposure history records
# durable healthy spans, never a row for each frame.
DURABLE_EXPOSURE_CHECKPOINT_INTERVAL = timedelta(seconds=45)

# Match the existing product health definition. A frame older than this cannot
# extend a healthy exposure interval.
DURABLE_EXPOSURE_FRESHNESS_LIMIT = timedelta(minutes=2)


def exposure_close_reason_for_transition(reason: str) -> str:
    """Map runtime transitions to a compact, credential-safe exposure boundary."""

    return {
        "policy_disabled": "monitoring_disabled",
        "manual_camera_stop": "monitoring_disabled",
        "api_shutdown": "application_shutdown",
        "repository_reconfigured": "application_shutdown",
        "local_backup_restore": "application_shutdown",
        "camera_configuration_changed": "session_stopped",
        "runtime_unhealthy": "provider_failure",
        "fresh_frame_stale": "fresh_frame_stale",
        "source_archived": "source_unusable",
    }.get(reason, "session_stopped")
