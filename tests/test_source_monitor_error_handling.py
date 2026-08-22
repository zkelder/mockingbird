"""`SourceMonitorManager._run`'s unexpected-failure boundary stays user-safe
(First-Hour Onboarding + Whole-Product Observability Closure v1, "B8 user-
safe actions"): a confirmed, live, traced defect this milestone's own
observability inventory found -- a raw `str(error)` used to reach
`StreamsPage.tsx`'s "Last error:" text verbatim, no curation.
"""

from __future__ import annotations

import pytest

from mockingbird.monitoring.source_monitor import (
    _MONITOR_LOOP_FAILURE_MESSAGE,
    _MonitorRecord,
    SourceMonitorManager,
    SourceMonitorState,
)


async def _never_called(*_args: object, **_kwargs: object) -> object:
    raise AssertionError("must not be called before _run_tick raises")


def _manager() -> SourceMonitorManager:
    return SourceMonitorManager(
        capture_snapshot=_never_called,
        list_saved_images=_never_called,
        evaluate_saved_media=_never_called,
    )


@pytest.mark.anyio
async def test_run_loop_failure_sets_a_safe_message_not_the_raw_exception_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager = _manager()
    state = SourceMonitorState(
        monitor_id="monitor-1", source_id="source-1", stream_id="stream-1", status="monitoring"
    )
    record = _MonitorRecord(state=state)

    async def _raising_run_tick(_record: _MonitorRecord) -> None:
        raise RuntimeError("a very specific internal detail that must never reach the user")

    monkeypatch.setattr(manager, "_run_tick", _raising_run_tick)

    await manager._run(record)

    assert record.state.last_error == _MONITOR_LOOP_FAILURE_MESSAGE
    assert "very specific internal detail" not in record.state.last_error
    assert "RuntimeError" not in record.state.last_error
    assert record.state.status == "error"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
