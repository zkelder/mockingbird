"""Structural tests for scripts/field_acceptance_client.py.

See docs/field-acceptance-evidence-integrity-storage-preflight-
correctness-v1-report.md for the governing milestone. Entirely hermetic:
no real network call anywhere in this file -- every test either
monkeypatches `urllib.request.urlopen` with a small in-memory fake, or
(for the defect this milestone actually reproduces) asserts the client
raises *before* `urlopen` would ever be reached at all.

Loaded via `runpy.run_path`, matching every other `scripts/` test file's
own established convention (`scripts/` is deliberately not a package).
"""

from __future__ import annotations

import json
from pathlib import Path
import runpy
import urllib.error
import urllib.request

import pytest

ROOT = Path(__file__).resolve().parents[1]
_MODULE = runpy.run_path(str(ROOT / "scripts" / "field_acceptance_client.py"))

FieldAcceptanceClient = _MODULE["FieldAcceptanceClient"]
FieldAcceptanceApiError = _MODULE["FieldAcceptanceApiError"]
FieldAcceptanceInvalidParameterError = _MODULE["FieldAcceptanceInvalidParameterError"]
FieldAcceptanceCredentialMissingError = _MODULE["FieldAcceptanceCredentialMissingError"]


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *exc_info: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


@pytest.fixture
def client() -> "FieldAcceptanceClient":
    return FieldAcceptanceClient(base_url="http://127.0.0.1:8000", token="test-token")


# ---------------------------------------------------------------------------
# Credential handling (sanity -- not the reproduced defect, but cheap to
# confirm the constructor still fails clearly with no token configured).
# ---------------------------------------------------------------------------


def test_constructor_requires_a_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MOCKINGBIRD_ACCEPTANCE_TOKEN", raising=False)
    with pytest.raises(FieldAcceptanceCredentialMissingError):
        FieldAcceptanceClient(base_url="http://127.0.0.1:8000")


# ---------------------------------------------------------------------------
# _request(): the generic query-building/None-filtering behavior -- correct
# and desired for a genuinely optional filter param (list_visits(limit=...)),
# and must keep working exactly this way; the fix belongs at the
# observation_counterfactual() call site, not here (see below).
# ---------------------------------------------------------------------------


def test_request_builds_a_query_string_from_params(
    client: "FieldAcceptanceClient", monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[urllib.request.Request] = []

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        captured.append(request)
        return _FakeResponse(json.dumps({"ok": True}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = client.list_visits(limit=5, stream_id="s1")

    assert result == {"ok": True}
    (request,) = captured
    assert request.full_url.startswith("http://127.0.0.1:8000/api/visits?")
    assert "limit=5" in request.full_url
    assert "stream_id=s1" in request.full_url
    assert request.get_header("Authorization") == "Bearer test-token"


def test_request_drops_none_valued_params_from_the_query_string(
    client: "FieldAcceptanceClient", monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The generic, desired behavior for an *optional* filter: `None`
    means "omit this from the query entirely," not "send the literal
    string 'None'." `observation_counterfactual`'s own bounds are
    deliberately never routed through this generic path -- see the tests
    below."""

    captured: list[urllib.request.Request] = []

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        captured.append(request)
        return _FakeResponse(b"[]")

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    client.list_visits(limit=None, stream_id="s1")

    (request,) = captured
    assert request.full_url == "http://127.0.0.1:8000/api/visits?stream_id=s1"
    assert "limit" not in request.full_url


# ---------------------------------------------------------------------------
# observation_counterfactual(): the exact Representative Daylight Gate A
# Field Acceptance v12 defect -- end_offset_ms=None silently dropped by
# _request, 422'd by the server on every one of 12 periodic snapshots.
# ---------------------------------------------------------------------------


def test_observation_counterfactual_rejects_none_end_offset_ms_before_any_request(
    client: "FieldAcceptanceClient", monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The exact v12 call shape: `observation_counterfactual(stream_id,
    start_offset_ms=0, end_offset_ms=None)`. Must fail locally, and must
    never reach the network at all -- asserted here by making `urlopen`
    itself raise if it is ever called, not merely by checking the
    exception type."""

    def _urlopen_must_not_be_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("observation_counterfactual must fail locally before any HTTP request")

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_must_not_be_called)

    with pytest.raises(FieldAcceptanceInvalidParameterError, match="end_offset_ms"):
        client.observation_counterfactual("stream-1", start_offset_ms=0, end_offset_ms=None)  # type: ignore[arg-type]


def test_observation_counterfactual_rejects_none_start_offset_ms_before_any_request(
    client: "FieldAcceptanceClient", monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _urlopen_must_not_be_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("observation_counterfactual must fail locally before any HTTP request")

    monkeypatch.setattr(urllib.request, "urlopen", _urlopen_must_not_be_called)

    with pytest.raises(FieldAcceptanceInvalidParameterError, match="start_offset_ms"):
        client.observation_counterfactual("stream-1", start_offset_ms=None, end_offset_ms=6_000_000)  # type: ignore[arg-type]


def test_observation_counterfactual_sends_both_bounds_when_explicit(
    client: "FieldAcceptanceClient", monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The intended, contract-correct form: an explicit, real
    `end_offset_ms` (e.g. a large fixed value, not None) -- see the
    governing report's 'Optional query semantics' finding: this endpoint
    has no omitted-bound form at all, so 'omitted' is never encoded, only
    ever refused (above)."""

    captured: list[urllib.request.Request] = []

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        captured.append(request)
        return _FakeResponse(json.dumps({"stream_id": "stream-1"}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = client.observation_counterfactual("stream-1", start_offset_ms=0, end_offset_ms=6_000_000)

    assert result == {"stream_id": "stream-1"}
    (request,) = captured
    assert request.full_url == (
        "http://127.0.0.1:8000/api/streams/stream-1/observation/counterfactual"
        "?start_offset_ms=0&end_offset_ms=6000000"
    )


def test_observation_counterfactual_zero_start_offset_is_not_mistaken_for_missing(
    client: "FieldAcceptanceClient", monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`start_offset_ms=0` is a genuine, common, explicit value (every
    real field-acceptance snapshot starts from 0) -- must never be
    treated as falsy/missing the way `if not start_offset_ms` would."""

    captured: list[urllib.request.Request] = []
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda request, timeout: captured.append(request) or _FakeResponse(b"{}"),
    )

    client.observation_counterfactual("stream-1", start_offset_ms=0, end_offset_ms=1000)

    assert "start_offset_ms=0" in captured[0].full_url


def test_observation_counterfactual_propagates_a_real_api_error(
    client: "FieldAcceptanceClient", monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sanity: a genuine server-side rejection (e.g. end precedes start)
    still surfaces as `FieldAcceptanceApiError`, unrelated to the local
    None-guard above."""

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        raise urllib.error.HTTPError(
            request.full_url, 400, "Bad Request",
            hdrs=None, fp=None,  # type: ignore[arg-type]
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    with pytest.raises(FieldAcceptanceApiError):
        client.observation_counterfactual("stream-1", start_offset_ms=1000, end_offset_ms=0)


# ---------------------------------------------------------------------------
# scene_confusor_learning_status(): additive client method for the new
# periodic-checkpoint tool's own "scene-confusor state" artifact class.
# ---------------------------------------------------------------------------


def test_scene_confusor_learning_status_calls_the_accepted_endpoint(
    client: "FieldAcceptanceClient", monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[urllib.request.Request] = []

    def fake_urlopen(request: urllib.request.Request, timeout: float) -> _FakeResponse:
        captured.append(request)
        return _FakeResponse(json.dumps({"stream_id": "stream-1", "reviewed_evidence_enabled": False}).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    result = client.scene_confusor_learning_status("stream-1")

    assert result == {"stream_id": "stream-1", "reviewed_evidence_enabled": False}
    (request,) = captured
    assert request.full_url == "http://127.0.0.1:8000/api/streams/stream-1/observation/scene-confusor-learning"
    assert request.get_method() == "GET"
