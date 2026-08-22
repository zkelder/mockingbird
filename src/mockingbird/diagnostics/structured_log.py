"""One small, bounded helper for structured operational log records.

Confirmed by direct code archaeology (see the observability inventory this
milestone's investigation produced): structured/JSON logging was absent
product-wide before this module -- the two pre-existing `logging` call sites
(`runtime.py`'s startup-failure handling) both use plain interpolated text.
This module does not build a logging service, a new transport, or a new
retention policy; it emits one structured record through the *existing*
root logger, which `runtime_state.configure_file_logging` already wires to
a correctly-bounded rotating file handler
(`<runtime home>/logs/mockingbird.log`, 5 MB x 4 files -- see
`runtime_state.py`). This module only adds *what* gets logged for a
representative set of currently-unlogged operational events, never a second
place logs are written to.

Never log image bytes, high-cardinality model vectors, or raw credentials.
`fields` values are expected to already be small, structured, and safe
(ids, codes, counts, durations) -- the same discipline the milestone brief
states directly: "Do not log every frame. No image bytes. No high-
cardinality model vectors."
"""

from __future__ import annotations

import json
import logging
from typing import Any

_STRUCTURED_LOGGER_NAME = "mockingbird.events"


def _event_logger() -> logging.Logger:
    # A dedicated child logger (not the bare root logger) so a future
    # operator can filter/route structured events independently of
    # uvicorn's own access/error logging, without a second handler/rotation
    # config -- it still propagates to the root logger's own handlers
    # (the rotating file handler `configure_file_logging` already installs)
    # by ordinary `logging` propagation, so no additional wiring is needed
    # for these records to reach the same bounded log file.
    return logging.getLogger(_STRUCTURED_LOGGER_NAME)


def log_event(
    component: str,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    """Emit one structured operational log record.

    `component` and `event` are short, stable, snake_case identifiers
    (e.g. `component="camera_node"`, `event="health_transition"`) --
    matching the taxonomy's own naming convention (see
    `diagnostics.error_taxonomy`) so a log line and a structured error can
    be correlated by eye. `fields` should carry only bounded identifiers
    (request_id/stream_id/source_id/event_id/visit_id where meaningful --
    never all of them on every line) and small scalar facts, never a full
    payload or image data.

    A field value that fails to JSON-encode is stringified rather than
    raising -- a logging call must never itself crash the caller's real
    work.
    """

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
    except (TypeError, ValueError):  # pragma: no cover - defensive, see docstring
        message = f"{component}.{event} {safe_fields!r}"
    _event_logger().log(level, message)


def log_error_event(
    component: str,
    event: str,
    *,
    code: str,
    exception: BaseException | None = None,
    **fields: Any,
) -> None:
    """`log_event` for a failure specifically: always includes the stable
    `code`, and -- only in this bounded, advanced-log-only place, never in
    a user-facing message -- a short exception summary when one is
    available. Mirrors `error_taxonomy.bounded_exception_detail`'s exact
    truncation so a log line can never itself grow unbounded from a long
    exception message."""

    from mockingbird.diagnostics.error_taxonomy import bounded_exception_detail

    if exception is not None:
        fields["exception"] = bounded_exception_detail(exception)
    log_event(component, event, level=logging.WARNING, code=code, **fields)
