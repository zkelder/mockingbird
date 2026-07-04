"""Dry-run helpers for generic webhook payload shape validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class WebhookCandidateSummary:
    candidate_type: str
    external_event_id: str | None = None
    external_label: str | None = None
    external_confidence: float | None = None
    media_reference: str | None = None
    message: str = ""
    warnings: list[str] = field(default_factory=list)
    valid: bool = True
    skipped_reason: str | None = None


_TYPE_TO_CANDIDATE = {
    "heartbeat": "heartbeat",
    "motion": "motion_event",
    "object": "object_detection",
    "species": "species_suggestion",
    "media": "media_reference",
}


def classify_webhook_payload(payload: Mapping[str, Any]) -> WebhookCandidateSummary:
    warnings: list[str] = []
    payload_type = _string_value(payload.get("type"))
    normalized_type = payload_type.lower() if payload_type else None
    candidate_type = _TYPE_TO_CANDIDATE.get(normalized_type or "", "unknown")

    external_event_id = _string_value(payload.get("external_event_id"))
    external_label = _string_value(payload.get("label"))
    external_confidence = _confidence_value(payload.get("confidence"), warnings)
    media_reference = _media_reference(payload, warnings)

    if external_label is not None:
        warnings.append("External labels are untrusted candidate metadata, not review truth.")
    if external_confidence is not None:
        warnings.append("External confidence is untrusted candidate metadata.")

    if normalized_type is None:
        return WebhookCandidateSummary(
            candidate_type="unknown",
            external_event_id=external_event_id,
            external_label=external_label,
            external_confidence=external_confidence,
            media_reference=media_reference,
            message="Webhook payload is missing a supported type.",
            warnings=warnings + ["Supported types are heartbeat, motion, object, species, and media."],
            valid=False,
            skipped_reason="missing_type",
        )

    if candidate_type == "unknown":
        return WebhookCandidateSummary(
            candidate_type="unknown",
            external_event_id=external_event_id,
            external_label=external_label,
            external_confidence=external_confidence,
            media_reference=media_reference,
            message=f"Webhook payload type '{payload_type}' is not supported.",
            warnings=warnings + ["Unknown webhook payload type; no records would be created."],
            valid=False,
            skipped_reason="unknown_type",
        )

    if candidate_type == "heartbeat":
        return WebhookCandidateSummary(
            candidate_type=candidate_type,
            external_event_id=external_event_id,
            external_label=external_label,
            external_confidence=external_confidence,
            media_reference=media_reference,
            message="Heartbeat payload validates as metadata/status only.",
            warnings=warnings,
        )

    if candidate_type == "media_reference" and media_reference is None:
        return WebhookCandidateSummary(
            candidate_type=candidate_type,
            external_event_id=external_event_id,
            external_label=external_label,
            external_confidence=external_confidence,
            media_reference=None,
            message="Media payload needs media_url or media_id metadata.",
            warnings=warnings,
            valid=False,
            skipped_reason="missing_media_reference",
        )

    messages = {
        "motion_event": "Motion payload validates as a future motion event candidate.",
        "object_detection": "Object payload validates as future detection evidence.",
        "species_suggestion": "Species payload validates as a future species suggestion.",
        "media_reference": "Media payload validates as a future media reference.",
    }
    return WebhookCandidateSummary(
        candidate_type=candidate_type,
        external_event_id=external_event_id,
        external_label=external_label,
        external_confidence=external_confidence,
        media_reference=media_reference,
        message=messages[candidate_type],
        warnings=warnings,
    )


def _string_value(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _confidence_value(value: Any, warnings: list[str]) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool):
        warnings.append("Webhook confidence was ignored because it is not numeric.")
        return None
    if isinstance(value, (int, float)):
        return float(value)
    warnings.append("Webhook confidence was ignored because it is not numeric.")
    return None


def _media_reference(payload: Mapping[str, Any], warnings: list[str]) -> str | None:
    media_id = _string_value(payload.get("media_id"))
    if media_id is not None:
        return media_id

    media_url = _string_value(payload.get("media_url"))
    if media_url is None:
        return None
    if media_url.startswith("/") or media_url.startswith("file:") or "\\" in media_url:
        warnings.append("Local file-like media references are not trusted as paths.")
        return "local_path_reference"
    warnings.append("Media URL is a dry-run string reference only; it was not fetched.")
    return media_url
