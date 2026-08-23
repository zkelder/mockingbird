"""Self-contained structured-log helper for the Camera Node package.

Mirrors `mockingbird.diagnostics.structured_log`'s shape and spirit
(component/event/**fields, JSON-encoded, WARNING for failures) so the two
halves of one product "feel" consistent -- but this package is built and
shipped independently of the main `mockingbird` package (see
`scripts/build_camera_node_artifact.py`: only `src/mockingbird_node/` is
bundled), and no file under `src/mockingbird_node/` imports from
`mockingbird.*` today. This module intentionally keeps that boundary
rather than reaching across it.
"""

from __future__ import annotations

import json
import logging
from typing import Any

_LOGGER_NAME = "mockingbird_node.events"


def _event_logger() -> logging.Logger:
    return logging.getLogger(_LOGGER_NAME)


def log_event(component: str, event: str, *, level: int = logging.INFO, **fields: Any) -> None:
    safe_fields: dict[str, Any] = {}
    for key, value in fields.items():
        try:
            json.dumps(value)
        except (TypeError, ValueError):
            value = str(value)
        safe_fields[key] = value
    record = {"component": component, "event": event, **safe_fields}
    try:
        message = json.dumps(record, default=str, sort_keys=True)
    except (TypeError, ValueError):  # pragma: no cover - defensive
        message = f"{component}.{event} {safe_fields!r}"
    _event_logger().log(level, message)


def log_error_event(component: str, event: str, *, code: str, **fields: Any) -> None:
    log_event(component, event, level=logging.WARNING, code=code, **fields)
