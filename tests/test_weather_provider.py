"""Pure computation tests for mockingbird.environment.weather_provider.

No repository, no database, no real network by default -- matches the
existing test_conditional_association.py precedent for a pure sibling
module. One opt-in real-network test at the bottom proves the parser
against the actual live Open-Meteo response shape captured during this
milestone's provider-selection research (see docs/environmental-context-
v2-contract.md "Phase 3").
"""

from __future__ import annotations

import json
import os
from datetime import UTC, date, datetime

import pytest

from mockingbird.environment import weather_provider
from mockingbird.environment.weather_provider import (
    ALL_WEATHER_METRICS,
    WEATHER_INFORMATION_CLASS,
    WEATHER_MAX_PAST_DAYS,
    WEATHER_PROVIDER_KEY,
    HourlyWeatherObservation,
    WeatherProviderMalformedResponseError,
    WeatherProviderRateLimitedError,
    WeatherProviderStatus,
    WeatherProviderTimeoutError,
    WeatherProviderUnavailableError,
    WeatherUnsupportedLocationError,
    build_hourly_request_url,
    fetch_hourly_weather,
    get_weather_provider_status,
    metric_api_field,
    parse_hourly_response,
)

FOR_DATE = date(2026, 8, 20)


def _canned_payload(*, hours: int = 24) -> dict:
    times = [f"{FOR_DATE.isoformat()}T{h:02d}:00" for h in range(hours)]
    return {
        "latitude": 40.71,
        "longitude": -73.99,
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
        "hourly": {
            "time": times,
            "temperature_2m": [20.0 + h * 0.1 for h in range(hours)],
            "relative_humidity_2m": [55.0 for _ in range(hours)],
            "precipitation": [0.0 for _ in range(hours)],
            "snowfall": [0.0 for _ in range(hours)],
            "wind_speed_10m": [12.0 for _ in range(hours)],
            "wind_direction_10m": [200.0 for _ in range(hours)],
            "cloud_cover": [40.0 for _ in range(hours)],
            "surface_pressure": [1012.0 for _ in range(hours)],
        },
    }


# ---------------------------------------------------------------------------
# get_weather_provider_status
# ---------------------------------------------------------------------------


def test_status_not_configured_when_coordinates_absent() -> None:
    status = get_weather_provider_status(None, None, weather_enabled=True)
    assert status == WeatherProviderStatus(
        status="not_configured", configured=False, enabled=True, detail=status.detail
    )


def test_status_disabled_when_coordinates_present_but_not_enabled() -> None:
    status = get_weather_provider_status(40.7, -74.0, weather_enabled=False)
    assert status.status == "disabled"
    assert status.configured is True
    assert status.enabled is False


def test_status_available_when_configured_and_enabled() -> None:
    status = get_weather_provider_status(40.7, -74.0, weather_enabled=True)
    assert status.status == "available"


def test_status_never_raises_on_partial_coordinates() -> None:
    # Defensive: the settings layer enforces both-or-neither, but this
    # module must never assume that invariant holds upstream.
    status = get_weather_provider_status(40.7, None, weather_enabled=True)
    assert status.status == "not_configured"


# ---------------------------------------------------------------------------
# build_hourly_request_url
# ---------------------------------------------------------------------------


def test_request_url_uses_single_date_as_both_start_and_end() -> None:
    url = build_hourly_request_url(40.7, -74.0, FOR_DATE)
    assert f"start_date={FOR_DATE.isoformat()}" in url
    assert f"end_date={FOR_DATE.isoformat()}" in url
    assert "timezone=UTC" in url
    assert url.startswith(weather_provider.WEATHER_API_BASE_URL)


def test_request_url_includes_every_metric_field() -> None:
    url = build_hourly_request_url(40.7, -74.0, FOR_DATE)
    for metric in ALL_WEATHER_METRICS:
        assert metric_api_field(metric) in url


def test_request_url_never_requests_a_future_forecast_parameter() -> None:
    # Phase 17: this product must never even request forecast data.
    url = build_hourly_request_url(40.7, -74.0, FOR_DATE)
    assert "forecast_days" not in url


# ---------------------------------------------------------------------------
# parse_hourly_response -- normal / missing field / malformed
# ---------------------------------------------------------------------------


def test_parse_normal_response_returns_one_observation_per_metric_per_hour() -> None:
    body = json.dumps(_canned_payload()).encode("utf-8")
    observations = parse_hourly_response(body, for_date=FOR_DATE)
    assert len(observations) == 24 * len(ALL_WEATHER_METRICS)
    assert all(isinstance(o, HourlyWeatherObservation) for o in observations)
    assert all(o.for_date == FOR_DATE for o in observations)
    temp_obs = [o for o in observations if o.metric == "air_temperature"]
    assert len(temp_obs) == 24
    assert temp_obs[0].value_numeric == pytest.approx(20.0)
    assert temp_obs[0].unit == "celsius"
    assert temp_obs[0].observed_at == datetime(2026, 8, 20, 0, 0, tzinfo=UTC)


def test_parse_tolerates_a_missing_field_entirely() -> None:
    payload = _canned_payload()
    del payload["hourly"]["surface_pressure"]
    observations = parse_hourly_response(json.dumps(payload).encode(), for_date=FOR_DATE)
    assert not any(o.metric == "surface_pressure" for o in observations)
    assert any(o.metric == "air_temperature" for o in observations)


def test_parse_skips_a_null_hour_for_one_metric_without_failing_others() -> None:
    payload = _canned_payload()
    payload["hourly"]["cloud_cover"][3] = None
    observations = parse_hourly_response(json.dumps(payload).encode(), for_date=FOR_DATE)
    cloud_hours = [o for o in observations if o.metric == "cloud_cover"]
    assert len(cloud_hours) == 23
    temp_hours = [o for o in observations if o.metric == "air_temperature"]
    assert len(temp_hours) == 24


def test_parse_raises_on_invalid_json() -> None:
    with pytest.raises(WeatherProviderMalformedResponseError):
        parse_hourly_response(b"not json at all {{{", for_date=FOR_DATE)


def test_parse_raises_when_hourly_key_missing() -> None:
    with pytest.raises(WeatherProviderMalformedResponseError):
        parse_hourly_response(json.dumps({"latitude": 1.0}).encode(), for_date=FOR_DATE)


def test_parse_raises_when_time_array_missing() -> None:
    with pytest.raises(WeatherProviderMalformedResponseError):
        parse_hourly_response(json.dumps({"hourly": {}}).encode(), for_date=FOR_DATE)


def test_parse_raises_when_field_length_mismatches_time_length() -> None:
    payload = _canned_payload()
    payload["hourly"]["temperature_2m"] = [1.0, 2.0]  # 24 times, 2 values
    with pytest.raises(WeatherProviderMalformedResponseError):
        parse_hourly_response(json.dumps(payload).encode(), for_date=FOR_DATE)


def test_parse_raises_on_non_numeric_value() -> None:
    payload = _canned_payload()
    payload["hourly"]["temperature_2m"][0] = "not-a-number"
    with pytest.raises(WeatherProviderMalformedResponseError):
        parse_hourly_response(json.dumps(payload).encode(), for_date=FOR_DATE)


def test_parse_raises_when_top_level_is_not_an_object() -> None:
    with pytest.raises(WeatherProviderMalformedResponseError):
        parse_hourly_response(json.dumps([1, 2, 3]).encode(), for_date=FOR_DATE)


# ---------------------------------------------------------------------------
# HTTP error taxonomy -- these are captured shapes from real Open-Meteo
# calls made during this milestone's provider-selection research (see the
# v2 contract's "Phase 3"), not guessed.
# ---------------------------------------------------------------------------


class _FakeHTTPErrorRequester:
    """Raises the same exception shape `UrlLibWeatherRequester._raise_for_
    http_error` would raise for a given status/body, without ever opening a
    socket -- used to prove `fetch_hourly_weather` propagates the right
    typed exception for each captured real error shape."""

    def __init__(self, status_code: int, body: bytes) -> None:
        self._status_code = status_code
        self._body = body

    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        weather_provider._raise_for_http_error(self._status_code, self._body)
        raise AssertionError("unreachable")


def test_rate_limited_maps_to_dedicated_exception() -> None:
    requester = _FakeHTTPErrorRequester(429, b'{"reason": "rate limit exceeded", "error": true}')
    with pytest.raises(WeatherProviderRateLimitedError):
        fetch_hourly_weather(40.7, -74.0, FOR_DATE, requester=requester, now=datetime.now(UTC))


def test_unsupported_latitude_maps_to_dedicated_exception() -> None:
    # Captured verbatim from a real Open-Meteo call during provider
    # research: {"reason":"Latitude must be in range of -90 to 90°.
    # Given: 999.0.","error":true}
    requester = _FakeHTTPErrorRequester(
        400, json.dumps({"reason": "Latitude must be in range of -90 to 90°. Given: 999.0.", "error": True}).encode()
    )
    with pytest.raises(WeatherUnsupportedLocationError):
        fetch_hourly_weather(999.0, -74.0, FOR_DATE, requester=requester, now=datetime.now(UTC))


def test_out_of_range_start_date_maps_to_malformed_not_unsupported_location() -> None:
    # Captured verbatim from a real Open-Meteo call: this is a MockingBird-
    # side bounds bug (the repository layer must never ask for a date
    # outside WEATHER_MAX_PAST_DAYS), not a location problem -- so it must
    # not be misclassified as WeatherUnsupportedLocationError.
    requester = _FakeHTTPErrorRequester(
        400,
        json.dumps(
            {"reason": "Parameter 'start_date' is out of allowed range from 2026-05-24 to 2026-09-09", "error": True}
        ).encode(),
    )
    with pytest.raises(WeatherProviderMalformedResponseError):
        fetch_hourly_weather(40.7, -74.0, FOR_DATE, requester=requester, now=datetime.now(UTC))


def test_server_error_maps_to_unavailable() -> None:
    requester = _FakeHTTPErrorRequester(503, b"")
    with pytest.raises(WeatherProviderUnavailableError):
        fetch_hourly_weather(40.7, -74.0, FOR_DATE, requester=requester, now=datetime.now(UTC))


class _TimeoutRequester:
    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        raise weather_provider.WeatherProviderTimeoutError("simulated timeout")


def test_timeout_propagates_as_dedicated_exception() -> None:
    with pytest.raises(WeatherProviderTimeoutError):
        fetch_hourly_weather(40.7, -74.0, FOR_DATE, requester=_TimeoutRequester(), now=datetime.now(UTC))


# ---------------------------------------------------------------------------
# fetch_hourly_weather (happy path, fake requester)
# ---------------------------------------------------------------------------


class _FakeRequester:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.calls: list[str] = []

    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        self.calls.append(url)
        return self.body


def test_fetch_hourly_weather_returns_result_with_basis_and_retrieved_at() -> None:
    requester = _FakeRequester(json.dumps(_canned_payload()).encode())
    now = datetime(2026, 8, 25, 12, 0, tzinfo=UTC)
    result = fetch_hourly_weather(40.7, -74.0, FOR_DATE, requester=requester, now=now)
    assert result.basis_latitude == 40.7
    assert result.basis_longitude == -74.0
    assert result.retrieved_at == now
    assert result.for_date == FOR_DATE
    assert len(requester.calls) == 1
    assert len(result.observations) == 24 * len(ALL_WEATHER_METRICS)


# ---------------------------------------------------------------------------
# Constants / vocabulary
# ---------------------------------------------------------------------------


def test_information_class_is_always_inferred() -> None:
    assert WEATHER_INFORMATION_CLASS == "inferred"


def test_provider_key_constant() -> None:
    assert WEATHER_PROVIDER_KEY == "open_meteo"


def test_max_past_days_matches_the_providers_own_confirmed_limit() -> None:
    # Confirmed via a real HTTP 400 during provider-selection research
    # naming the exact allowed window -- see the v2 contract's "Phase 3".
    assert WEATHER_MAX_PAST_DAYS == 92


def test_all_metrics_have_a_stable_provider_neutral_vocabulary() -> None:
    assert set(ALL_WEATHER_METRICS) == {
        "air_temperature",
        "relative_humidity",
        "precipitation_amount",
        "snowfall_amount",
        "wind_speed",
        "wind_direction",
        "cloud_cover",
        "surface_pressure",
    }


# ---------------------------------------------------------------------------
# Opt-in real-network smoke test -- mirrors this repository's convention for
# tests that need genuine internet access (skipped by default, never part
# of the normal fast suite). Set MOCKINGBIRD_TEST_REAL_WEATHER_NETWORK=1 to
# run it.
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    os.environ.get("MOCKINGBIRD_TEST_REAL_WEATHER_NETWORK") != "1",
    reason="opt-in real-network test; set MOCKINGBIRD_TEST_REAL_WEATHER_NETWORK=1 to run",
)
def test_real_open_meteo_call_returns_a_parseable_response() -> None:
    from datetime import timedelta

    real_requester = weather_provider.UrlLibWeatherRequester()
    yesterday = datetime.now(UTC).date() - timedelta(days=1)
    result = fetch_hourly_weather(40.7, -74.0, yesterday, requester=real_requester, now=datetime.now(UTC))
    assert len(result.observations) > 0
    assert any(o.metric == "air_temperature" for o in result.observations)
