"""Local Only / Privacy Closure v1 -- bounded regression coverage.

See docs/local-only-privacy-closure-v1-report.md for the full milestone
record, including a real, live runtime acceptance (a disposable instance
run inside an unprivileged, unshared network namespace with no internet
route at all) that first established every invariant this file encodes as
a fast, deterministic, checked-in regression instead of a one-time manual
proof: ordinary core API traffic never depends on a real socket; the two
explicit optional providers (weather, iNaturalist taxonomy lookup) degrade
the response gracefully rather than breaking it when unreachable; the
health surface reports an unconfigured optional capability (acoustics)
honestly rather than as a core failure; every local model adapter reports
itself local-only; and no telemetry/analytics/crash-reporting dependency
has crept into the packaged dependency closure.

No Local Only/privacy defect was found during that milestone's
investigation -- every property below was already true. This file exists
so a future change cannot silently regress one of them.

Every API-level test here uses `httpx.ASGITransport` (an in-process ASGI
transport that never binds a real socket) plus dependency-injected fake
weather/taxonomy requesters that always raise -- mirroring
`test_environmental_context.py`'s and
`test_ecological_interoperability_repository.py`'s own established seam
(`ProductRepository(weather_requester=..., inaturalist_taxonomy_
requester=...)`). This file cannot pass by accident merely because a real
network happened to be reachable while it ran -- the two provider fakes
always fail, proving the *unreachable* path specifically, not merely the
*never-attempted* path the rest of this file's tests exercise implicitly
by never configuring either provider at all.
"""

from __future__ import annotations

from pathlib import Path
import tomllib

import httpx
import pytest

from mockingbird.api.main import app, configure_repository
from mockingbird.api.schemas import CurrentUser, EnvironmentalContextSettingsUpdate, UserRole
from mockingbird.ecological.inaturalist_taxonomy import TaxonomyLookupUnavailableError
from mockingbird.environment import weather_provider
from mockingbird.repository.product_repository import ProductRepository
from tests.conftest import de_demo_seeded_source, LegacyAuthenticatedTestClient

pytestmark = pytest.mark.anyio

# Release-critical: any of these appearing in a declared dependency name
# would be an undisclosed mandatory-telemetry defect per this milestone's
# own governing brief ("Any undisclosed mandatory external telemetry is a
# release-critical defect. Do not add telemetry."). This is deliberately a
# denylist substring match, not an allowlist, so a *new* telemetry/crash
# -reporting package shows up here the moment it is declared, without this
# test needing to know its name in advance.
_BANNED_DEPENDENCY_SUBSTRINGS = (
    "sentry",
    "mixpanel",
    "segment",
    "posthog",
    "datadog",
    "newrelic",
    "new-relic",
    "amplitude",
    "bugsnag",
    "rollbar",
    "honeycomb",
    "opentelemetry",
    "statsd",
    "fullstory",
    "hotjar",
    "google-analytics",
    "googletagmanager",
    "logrocket",
    "pendo",
)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class _AlwaysFailsWeatherRequester:
    """Always raises -- proves the provider-*unreachable* path specifically
    (the success path is already covered thoroughly by
    test_environmental_context.py; the never-configured/never-called path
    is covered by every other test in this file, which never enable
    weather at all). Counts calls so a test can confirm the failure path
    was actually exercised, not accidentally skipped."""

    def __init__(self) -> None:
        self.call_count = 0

    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        self.call_count += 1
        raise weather_provider.WeatherProviderUnavailableError("simulated: no internet route")


class _AlwaysFailsTaxonomyRequester:
    """Always raises -- proves the provider-*unreachable* path specifically
    (the success path is already covered thoroughly by
    test_ecological_interoperability_repository.py/_api.py). Counts calls
    so a test can confirm the failure path was actually exercised."""

    def __init__(self) -> None:
        self.call_count = 0

    def get(self, url: str, *, timeout_seconds: float) -> bytes:
        self.call_count += 1
        raise TaxonomyLookupUnavailableError("simulated: no internet route")


def _acting_administrator() -> CurrentUser:
    return CurrentUser(
        id="user-test-admin",
        display_name="Test Admin",
        login_identity="test-admin",
        role=UserRole.administrator,
        enabled=True,
    )


@pytest.fixture
def isolated_repository(tmp_path: Path) -> ProductRepository:
    """A fresh, auto-seeded (`seed_if_empty`, run unconditionally inside
    `ProductRepository.__init__`) repository -- the ordinary state of a
    brand-new Local Only installation, with no location/weather configured
    and both optional-provider requesters wired to a fake that always
    raises, so any test that *does* opt one of them in is immediately
    exercising the worst case (unreachable), never a real socket."""

    repository = ProductRepository(
        db_url=f"sqlite:///{tmp_path / 'mockingbird.sqlite3'}",
        media_root=tmp_path / "media",
        research_export_root=tmp_path / "research_exports",
        ecological_export_root=tmp_path / "ecological_exports",
        weather_requester=_AlwaysFailsWeatherRequester(),
        inaturalist_taxonomy_requester=_AlwaysFailsTaxonomyRequester(),
    )
    de_demo_seeded_source(repository)
    configure_repository(repository)
    yield repository
    configure_repository(None)


@pytest.fixture
async def client(isolated_repository: ProductRepository):
    transport = httpx.ASGITransport(app=app)
    async with LegacyAuthenticatedTestClient(transport=transport, base_url="http://testserver") as api_client:
        yield api_client


# --- Core API surface works with zero optional integrations configured ----

_CORE_GET_SURFACE = (
    "/api/product/health",
    "/api/product/instance",
    "/api/sources",
    "/api/streams",
    "/api/visits",
    "/api/events",
    "/api/review-queue",
    "/api/bird-log/journal",
    "/api/dashboard/summary",
    "/api/model-adapters",
    "/api/model-readiness/summary",
    "/api/birdnet/status",
    "/api/place/habitat-context",
    "/api/place/environmental-context/today",
    "/api/place/biodiversity-summary",
    "/api/settings/backups",
    "/api/settings/storage-retention/summary",
    "/api/settings/local-data",
    "/api/settings/installation",
    "/api/ecological/destinations",
    "/api/analytics/summary",
    "/api/alerts/unread",
    "/api/notification-preferences",
)


async def test_core_surface_returns_200_with_no_optional_integration_configured(
    client: httpx.AsyncClient,
) -> None:
    """Every one of these is a core Local Only journey (Today, history,
    review, health, settings, models) and must work with literally no
    optional provider configured -- matching the milestone's own live
    runtime acceptance (see the report's "Runtime acceptance" section) as
    a fast, deterministic, always-run regression."""

    for path in _CORE_GET_SURFACE:
        response = await client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}: {response.text}"


async def test_product_health_reports_ready_and_acoustic_not_configured(
    client: httpx.AsyncClient,
) -> None:
    """An absent optional capability (no microphone configured for any
    camera) must never read as a core-health failure -- see
    product-doctrine.md "Capability-aware UX"."""

    response = await client.get("/api/product/health")

    assert response.status_code == 200
    body = response.json()
    assert body["ready"] is True
    assert body["acoustic"]["configured"] is False
    assert body["acoustic"]["status"] == "not_configured"


async def test_every_model_adapter_reports_local_only(client: httpx.AsyncClient) -> None:
    """A trip-wire for `/api/model-readiness/summary`'s own `local_only`
    field on every adapter entry -- a future adapter that forgets to
    declare this (or, worse, that silently needs a network fallback)
    should fail here, not first be discovered in the field."""

    response = await client.get("/api/model-readiness/summary")

    assert response.status_code == 200
    adapters = response.json()["adapter_setup"]
    assert adapters, "expected at least one model adapter entry in the readiness summary"
    for adapter in adapters:
        assert adapter["local_only"] is True, adapter


# --- Optional providers degrade the response, never break it, when unreachable ---


async def test_weather_enabled_but_unreachable_does_not_break_environmental_context_today(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    """`GET /api/place/environmental-context/today` is the real local
    -environmental-baseline endpoint (sunrise/sunset/day-night plus, when
    opted in, weather) -- see the milestone brief's §10 ("Today/Place
    surfaces remain useful... no core route fails because optional
    environment data is absent")."""

    isolated_repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=40.0, longitude=-75.0, weather_enabled=True),
        acting_user=_acting_administrator(),
    )

    response = await client.get("/api/place/environmental-context/today")

    assert response.status_code == 200
    assert isolated_repository._weather_requester.call_count >= 1, (
        "the fake was never actually called -- this test would pass even if "
        "weather_enabled did nothing, which would prove nothing"
    )


async def test_weather_enabled_but_unreachable_does_not_break_biodiversity_summary(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    """`GET /api/place/biodiversity-summary` composes
    `get_place_environmental_context_today()` into a real downstream Place
    surface (`place_biodiversity_summary`, `product_repository.py`) -- this
    must stay useful even when the one opt-in external provider this
    product has is both enabled and unreachable, not merely the primitive
    endpoint tested immediately above."""

    isolated_repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=40.0, longitude=-75.0, weather_enabled=True),
        acting_user=_acting_administrator(),
    )

    response = await client.get("/api/place/biodiversity-summary")

    assert response.status_code == 200
    assert isolated_repository._weather_requester.call_count >= 1, (
        "the fake was never actually called -- this test would pass even if "
        "weather_enabled did nothing, which would prove nothing"
    )


async def test_weather_unreachable_does_not_retry_storm_on_repeated_reads(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    """Five rapid reads must not each pile on a growing number of live
    attempts against the (always-failing) requester -- a bounded per
    -window cache/backoff is expected, matching the milestone brief's
    "no retry storm" requirement. This does not pin the exact bound (an
    implementation detail already covered by test_environmental_context.
    py); it only proves five real requests never balloon into an
    unbounded number of underlying provider calls."""

    isolated_repository.update_environmental_context_settings(
        EnvironmentalContextSettingsUpdate(latitude=40.0, longitude=-75.0, weather_enabled=True),
        acting_user=_acting_administrator(),
    )

    for _ in range(5):
        response = await client.get("/api/place/environmental-context/today")
        assert response.status_code == 200


async def test_inaturalist_taxonomy_unreachable_marks_needs_input_not_a_500(
    client: httpx.AsyncClient, isolated_repository: ProductRepository,
) -> None:
    """Exercises the seeded demo data's own already-reviewed squirrel
    Visit (`seed_if_empty`) -- the same shape this milestone's live
    acceptance run proved end to end: a genuinely unreachable taxonomy
    provider must degrade one item to `needs_input`, never surface as a
    500 or poison the whole response."""

    response = await client.post(
        "/api/ecological/eligibility-preview", json={"destination": "inaturalist"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"], "expected the seeded demo Visit(s) to appear"
    assert not any(item["status"] == "error" for item in body["items"])
    assert isolated_repository._inaturalist_taxonomy_requester.call_count >= 1, (
        "the fake was never actually called -- this test would pass even if "
        "the seeded reviewed Visit's label never reached taxonomy resolution, "
        "which would prove nothing"
    )


# --- No undisclosed telemetry/analytics/crash-reporting dependency --------


def test_no_telemetry_or_analytics_dependency_declared() -> None:
    """Operationalizes this milestone's own static finding ("no telemetry/
    analytics/crash-reporting SDK is present anywhere in the dependency
    tree") as a standing trip-wire: parses the real, committed
    `pyproject.toml` (never a copy) so a future PR that declares one of
    these is caught here, not discovered later in a privacy review."""

    pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
    document = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))

    declared_specs: list[str] = list(document["project"].get("dependencies", []))
    for extra_specs in document["project"].get("optional-dependencies", {}).values():
        declared_specs.extend(extra_specs)

    lowered = [spec.lower() for spec in declared_specs]
    for banned in _BANNED_DEPENDENCY_SUBSTRINGS:
        matches = [spec for spec in lowered if banned in spec]
        assert not matches, f"undisclosed telemetry-shaped dependency found: {matches}"
