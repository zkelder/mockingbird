"""Open-Meteo hourly weather provider (Environmental Context v2 -- see
docs/environmental-context-v2-contract.md "Phase 2/3/5/9").

Provider-neutral metric vocabulary, mapped from Open-Meteo's own field
names at the parsing boundary (`_METRIC_FIELD_MAP`) -- the rest of this
product never sees an Open-Meteo field name. `information_class` is always
`"inferred"` (never `"measured"`): every value here is a gridded/
interpolated numerical-weather-prediction estimate for the Place's
coordinate, not a direct physical-sensor reading, including "current"
conditions -- the same reasoning docs/environmental-context-foundation-v1-
contract.md already applied to deterministic solar computation, extended to
a genuinely probabilistic external estimate (see product-doctrine.md
"Measured, Inferred, and Reviewed").

Networking follows the existing house convention
(`mockingbird.source_providers.external_url_preview`/`onvif_client`): a
small bounded timeout, a dependency-injected requester `Protocol` for
testability without real sockets, one attempt, no retry/backoff, and every
failure degrades to a typed exception the repository layer converts to an
honest unavailable status -- never a raised exception reaching API/UI code,
never a crash, never a fabricated value. No new dependency: `urllib.request`
(stdlib) only, matching `external_url_preview.py`.

All request/response shapes below were confirmed this session via real,
unauthenticated HTTPS calls to `api.open-meteo.com` (see the v2 contract's
"Phase 3 -- provider selection" for the exact captured request/response/
error examples this module's parser and error taxonomy are built from).
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal, Protocol

WEATHER_PROVIDER_KEY = "open_meteo"
WEATHER_INFORMATION_CLASS = "inferred"
WEATHER_API_BASE_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_ALGORITHM_ID = "open_meteo_forecast_api"

# Confirmed this session via a real HTTP 400 naming the exact allowed
# window ("Parameter 'start_date' is out of allowed range from <today-92d>
# to <today+16d>"). This is the provider's own limit, not a MockingBird
# policy choice on top of a larger available window -- see the v2
# contract's "Phase 4/25" for why no archive/ERA5 integration is added to
# reach further back.
WEATHER_MAX_PAST_DAYS = 92

DEFAULT_TIMEOUT_SECONDS = 5.0

WeatherMetric = Literal[
    "air_temperature",
    "relative_humidity",
    "precipitation_amount",
    "snowfall_amount",
    "wind_speed",
    "wind_direction",
    "cloud_cover",
    "surface_pressure",
]

# Provider-neutral metric -> (Open-Meteo hourly field name, canonical unit).
# The canonical unit is always Open-Meteo's own metric default (no
# `*_unit=` query parameters are ever sent) -- one fixed internal unit per
# metric, conversion (e.g. to Fahrenheit) is a presentation-layer concern,
# never stored.
_METRIC_FIELD_MAP: dict[WeatherMetric, tuple[str, str]] = {
    "air_temperature": ("temperature_2m", "celsius"),
    "relative_humidity": ("relative_humidity_2m", "percent"),
    "precipitation_amount": ("precipitation", "mm"),
    "snowfall_amount": ("snowfall", "cm"),
    "wind_speed": ("wind_speed_10m", "km/h"),
    "wind_direction": ("wind_direction_10m", "degrees"),
    "cloud_cover": ("cloud_cover", "percent"),
    "surface_pressure": ("surface_pressure", "hPa"),
}

ALL_WEATHER_METRICS: tuple[WeatherMetric, ...] = tuple(_METRIC_FIELD_MAP.keys())


def metric_api_field(metric: WeatherMetric) -> str:
    """The Open-Meteo hourly field name that produces this provider-neutral
    metric -- exposed only for bounded provenance recording (see the
    repository's write path), never for building a request outside this
    module (`build_hourly_request_url` already owns the full field list)."""

    return _METRIC_FIELD_MAP[metric][0]


WeatherProviderStatusValue = Literal["available", "not_configured", "disabled", "unavailable"]


class WeatherProviderError(Exception):
    """Base for every failure this module raises. The repository layer
    catches this (never a narrower or broader exception type) and converts
    it to an honest unavailable status -- see docs/environmental-context-
    v2-contract.md "Phase 9 -- failure / degraded mode"."""


class WeatherProviderTimeoutError(WeatherProviderError):
    """The request did not complete within `timeout_seconds`."""


class WeatherProviderUnavailableError(WeatherProviderError):
    """Connection failure, DNS failure, or an HTTP 5xx response."""


class WeatherProviderRateLimitedError(WeatherProviderError):
    """HTTP 429. Kept distinct from a generic unavailable error so a future
    diagnostics surface can say "rate limited" rather than a generic
    failure -- see Phase 9."""


class WeatherUnsupportedLocationError(WeatherProviderError):
    """HTTP 400 whose body names a latitude/longitude range problem.
    Defensive only: MockingBird's own settings layer already range-
    validates coordinates before they can ever reach this module, so this
    should be unreachable in practice."""


class WeatherProviderMalformedResponseError(WeatherProviderError):
    """HTTP 200 with a body that is not valid JSON, or is valid JSON
    missing the expected `hourly`/`hourly_units` shape, or whose per-metric
    array length does not match `hourly.time`'s length."""


@dataclass(frozen=True)
class WeatherProviderStatus:
    """Side-effect-free readiness summary, mirroring `BioClipAdapterStatus`/
    `SolarContextStatus`'s identical shape for the same product-level
    question: "can this feature do anything useful right now." Never
    raises."""

    status: WeatherProviderStatusValue
    configured: bool
    enabled: bool
    detail: str


def get_weather_provider_status(
    latitude: float | None, longitude: float | None, *, weather_enabled: bool
) -> WeatherProviderStatus:
    """Never raises. Distinguishes "no location configured" from "location
    configured but the user has not opted in to outbound weather requests"
    -- two different reasons a caller sees no weather data, both real,
    neither collapsed into the other (see the v2 contract's "Privacy /
    location" reasoning: configuring coordinates for local solar computation
    must never silently also start sending them to a third party)."""

    if latitude is None or longitude is None:
        return WeatherProviderStatus(
            status="not_configured",
            configured=False,
            enabled=weather_enabled,
            detail="No approximate location is configured for this installation.",
        )
    if not weather_enabled:
        return WeatherProviderStatus(
            status="disabled",
            configured=True,
            enabled=False,
            detail="Weather context is not enabled for this installation.",
        )
    return WeatherProviderStatus(
        status="available",
        configured=True,
        enabled=True,
        detail="Weather context is enabled.",
    )


@dataclass(frozen=True)
class HourlyWeatherObservation:
    """One provider-neutral hourly fact. `observed_at` is always UTC-aware.
    `for_date` is the UTC calendar date `observed_at` falls on -- always
    populated (unlike solar's `for_date`, which is `NULL` for a metric with
    no natural single day), since every weather metric here is naturally
    daily-bucketed and this is the repository's cache-lookup key."""

    metric: WeatherMetric
    value_numeric: float
    unit: str
    observed_at: datetime
    for_date: date


@dataclass(frozen=True)
class WeatherFetchResult:
    """The result of one bounded, single-UTC-calendar-date fetch."""

    for_date: date
    observations: tuple[HourlyWeatherObservation, ...]
    retrieved_at: datetime
    basis_latitude: float
    basis_longitude: float


class WeatherRequester(Protocol):
    """Dependency-injection seam so tests never open a real socket --
    mirrors `onvif_client.OnvifRequester`'s identical shape."""

    def get(self, url: str, *, timeout_seconds: float) -> bytes: ...


class UrlLibWeatherRequester:
    """The real, production `WeatherRequester`: stdlib `urllib.request`
    only, matching `external_url_preview.py`'s existing convention -- no new
    HTTP-client dependency."""

    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        request = urllib.request.Request(url, headers={"User-Agent": "MockingBird/1.0"})
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read()
            _raise_for_http_error(exc.code, body)
            raise  # pragma: no cover -- _raise_for_http_error always raises
        except TimeoutError as exc:
            raise WeatherProviderTimeoutError(
                f"Weather provider request timed out after {timeout_seconds}s"
            ) from exc
        except urllib.error.URLError as exc:
            raise WeatherProviderUnavailableError(
                f"Weather provider request failed: {exc.reason}"
            ) from exc


def _raise_for_http_error(status_code: int, body: bytes) -> None:
    reason = _extract_error_reason(body)
    reason_lower = reason.lower() if reason is not None else ""
    if status_code == 429:
        raise WeatherProviderRateLimitedError(reason or "Weather provider rate limit exceeded")
    if status_code == 400 and ("latitude" in reason_lower or "longitude" in reason_lower):
        raise WeatherUnsupportedLocationError(reason)
    if 500 <= status_code < 600:
        raise WeatherProviderUnavailableError(reason or f"Weather provider returned HTTP {status_code}")
    # Any other 4xx (including a MockingBird-side bug requesting an
    # out-of-range date, which the repository layer must prevent before
    # ever calling this module -- see Phase 4/25) is treated as malformed
    # rather than invented a new category for a case that should be
    # unreachable in production.
    raise WeatherProviderMalformedResponseError(
        reason or f"Weather provider returned unexpected HTTP {status_code}"
    )


def _extract_error_reason(body: bytes) -> str | None:
    try:
        payload = json.loads(body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    if isinstance(payload, dict) and isinstance(payload.get("reason"), str):
        return payload["reason"]
    return None


def build_hourly_request_url(latitude: float, longitude: float, for_date: date) -> str:
    """Exactly one UTC calendar date per request -- see the v2 contract's
    "Phase 10/29" for why this bounded-simplicity choice (one request per
    not-yet-cached date, never a padded/batched range) was made over a
    premature batching optimization."""

    fields = ",".join(field for field, _unit in _METRIC_FIELD_MAP.values())
    params = {
        "latitude": f"{latitude:.4f}",
        "longitude": f"{longitude:.4f}",
        "hourly": fields,
        "start_date": for_date.isoformat(),
        "end_date": for_date.isoformat(),
        "timezone": "UTC",
    }
    return f"{WEATHER_API_BASE_URL}?{urllib.parse.urlencode(params)}"


def parse_hourly_response(payload_bytes: bytes, *, for_date: date) -> tuple[HourlyWeatherObservation, ...]:
    """Pure parsing, directly testable with canned JSON (normal/missing-
    field/malformed) -- no network access. Raises
    `WeatherProviderMalformedResponseError` for any shape that does not
    match what a real Open-Meteo response looks like (confirmed this
    session); never returns a partial/guessed result silently."""

    try:
        payload = json.loads(payload_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise WeatherProviderMalformedResponseError("Weather provider response was not valid JSON") from exc

    if not isinstance(payload, dict):
        raise WeatherProviderMalformedResponseError("Weather provider response was not a JSON object")

    hourly = payload.get("hourly")
    if not isinstance(hourly, dict):
        raise WeatherProviderMalformedResponseError("Weather provider response is missing 'hourly'")

    times = hourly.get("time")
    if not isinstance(times, list) or not times:
        raise WeatherProviderMalformedResponseError("Weather provider response is missing 'hourly.time'")

    try:
        parsed_times = [datetime.fromisoformat(t).replace(tzinfo=timezone.utc) for t in times]
    except (TypeError, ValueError) as exc:
        raise WeatherProviderMalformedResponseError(
            "Weather provider response has an unparsable 'hourly.time' entry"
        ) from exc

    observations: list[HourlyWeatherObservation] = []
    for metric, (field_name, unit) in _METRIC_FIELD_MAP.items():
        values = hourly.get(field_name)
        if values is None:
            # A missing field entirely is tolerated -- not every field is
            # guaranteed present in every response (e.g. a future Open-Meteo
            # response shape change) -- absence of one metric must never
            # invalidate the others (Phase 9: never let one bad field block
            # the whole fetch).
            continue
        if not isinstance(values, list) or len(values) != len(parsed_times):
            raise WeatherProviderMalformedResponseError(
                f"Weather provider response field '{field_name}' length does not match 'hourly.time'"
            )
        for observed_at, value in zip(parsed_times, values):
            if value is None:
                # Open-Meteo represents a genuine data gap as JSON null for
                # that hour -- skip that single hour/metric, never fabricate
                # a zero.
                continue
            if not isinstance(value, (int, float)):
                raise WeatherProviderMalformedResponseError(
                    f"Weather provider response field '{field_name}' contained a non-numeric value"
                )
            observations.append(
                HourlyWeatherObservation(
                    metric=metric,
                    value_numeric=float(value),
                    unit=unit,
                    observed_at=observed_at,
                    for_date=observed_at.date(),
                )
            )
    return tuple(observations)


def fetch_hourly_weather(
    latitude: float,
    longitude: float,
    for_date: date,
    *,
    requester: WeatherRequester,
    now: datetime,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> WeatherFetchResult:
    """One bounded HTTP call for one UTC calendar date. Raises a
    `WeatherProviderError` subclass on any failure -- callers (the
    repository layer) must catch `WeatherProviderError` and degrade
    honestly, never let this propagate to API/UI code."""

    url = build_hourly_request_url(latitude, longitude, for_date)
    body = requester.get(url, timeout_seconds=timeout_seconds)
    observations = parse_hourly_response(body, for_date=for_date)
    return WeatherFetchResult(
        for_date=for_date,
        observations=observations,
        retrieved_at=now,
        basis_latitude=latitude,
        basis_longitude=longitude,
    )


__all__ = [
    "WEATHER_PROVIDER_KEY",
    "WEATHER_INFORMATION_CLASS",
    "WEATHER_API_BASE_URL",
    "WEATHER_ALGORITHM_ID",
    "WEATHER_MAX_PAST_DAYS",
    "DEFAULT_TIMEOUT_SECONDS",
    "WeatherMetric",
    "ALL_WEATHER_METRICS",
    "metric_api_field",
    "WeatherProviderStatusValue",
    "WeatherProviderError",
    "WeatherProviderTimeoutError",
    "WeatherProviderUnavailableError",
    "WeatherProviderRateLimitedError",
    "WeatherUnsupportedLocationError",
    "WeatherProviderMalformedResponseError",
    "WeatherProviderStatus",
    "get_weather_provider_status",
    "HourlyWeatherObservation",
    "WeatherFetchResult",
    "WeatherRequester",
    "UrlLibWeatherRequester",
    "build_hourly_request_url",
    "parse_hourly_response",
    "fetch_hourly_weather",
]
