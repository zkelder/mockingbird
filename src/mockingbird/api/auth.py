"""Local human authentication and authorization (Local Identity, Multi-User
& Organization Access v1; see docs/local-identity-multi-user-contract.md).

A separately-owned module -- mirroring `camera_node_transport.py`'s own
precedent (its module docstring gives the same reason: keep this branch's
footprint in the large, concurrently-edited `main.py` to a minimum) -- for
a genuinely new cross-cutting surface: session cookies, the Viewer <
Reviewer < Administrator role ladder, and the one central authorization
gate every `/api/*` request passes through.

Design notes (see docs/local-identity-multi-user-contract.md for the full
rationale):

* Sessions are opaque and server-side (a random cookie token, only its
  SHA-256 hash ever persisted) rather than a self-contained token like a
  JWT -- this is what lets a disabled user or a role change take effect on
  the very next request with no separate revocation/blocklist step (every
  request re-reads the live `UserModel` row via `ProductRepository.
  resolve_session`).
* `Depends()` is never used anywhere in this codebase (confirmed by direct
  archaeology: 271 existing endpoints all call the module-level
  `get_repository()` singleton directly). The authorization gate below
  follows the codebase's own established idiom instead -- a single
  `@app.middleware("http")` function (mirroring the existing request-
  correlation-id middleware) that resolves the caller's identity once and
  stores it on `request.state.current_user`, exactly like `request.state.
  request_id` already works. A handler that needs the caller's identity
  (review attribution, audit entries) simply takes `request: Request` and
  reads `request.state.current_user`.
* The policy table below is deliberately a flat, explicit, hand-written
  `(method, path template) -> tier` mapping -- not a regex/prefix scheme
  generated from route introspection. Given the security stakes, an
  explicit, fully-auditable table that a reviewer can read top to bottom
  is worth more here than a cleverer mechanism. Matching an *incoming*
  request against this table still reuses Starlette's own real route
  matcher (`Route.matches`, confirmed against this project's installed
  Starlette version) rather than a hand-rolled path-template parser, so
  there is no risk of the gate's idea of "which route is this" ever
  diverging from what the router itself would actually dispatch to.
* Every `/api/*` path defaults to `authenticated` (any signed-in, enabled
  user -- the Viewer floor) unless explicitly listed as `public`,
  `device`, `reviewer`, or `administrator` below. This means a mutation
  endpoint accidentally left out of the `reviewer`/`administrator` tables
  is never fully open -- at worst it is reachable by a signed-in Viewer,
  never by an unauthenticated caller. See docs/local-identity-multi-user-
  contract.md "Authorization" for the full endpoint-by-endpoint
  classification and reasoning.
* This gate enforces the real policy unconditionally -- production request
  handling never infers "a test is running" from `PYTEST_CURRENT_TEST`,
  `sys.modules`, or any other ambient/environment signal, and there is no
  implicit synthetic actor anywhere in this module. Normal app construction
  (`install_authorization` called once, the same way, from `main.py`) always
  enforces this policy; nothing about this module changes shape depending on
  who imported it. ~100 test files predate this milestone and call
  protected endpoints over real HTTP with no session of their own -- their
  needed session is now minted by test infrastructure instead
  (`tests.conftest.LegacyAuthenticatedTestClient`), via genuine
  `POST /api/setup/administrator` bootstrap + `POST /api/auth/sign-in`
  calls, deliberately chosen by that test file's own fixture construction
  -- never by this module. See `tests/test_local_identity_multi_user.py`
  for the tests that instead exercise this real policy directly (real
  401/403, real role/disable/session behavior).

Non-Interactive Field Acceptance Authentication & Session Access v1 (see
docs/non-interactive-field-acceptance-authentication-session-access-v1-
contract.md) later added a second, narrow, parallel identity to this same
gate: a bearer-token field-acceptance credential, resolved independently of
the cookie-based `current_user` above and never merged into it (see
`FieldAcceptanceCredentialModel`'s own docstring for why it is deliberately
not a `UserModel`/role-ladder identity). It satisfies the `authenticated`
tier like any signed-in human, plus the small, explicit `FIELD_ACCEPTANCE_
ALLOWED_ADMIN_ROUTES` carve-out below (Observation start/stop only) --
nothing else Administrator- or Reviewer-tier. See `tests/test_field_
acceptance_authentication.py` for its own direct real-HTTP policy tests.
"""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.routing import Match

from mockingbird.api.schemas import (
    AdminPasswordResetRequest,
    AuditLogEntry,
    CurrentUser,
    FieldAcceptanceCredentialCreate,
    FieldAcceptanceCredentialCreated,
    FieldAcceptanceCredentialSummary,
    FieldAcceptancePrincipal,
    InstallationSettings,
    InstallationSettingsUpdate,
    SelfPasswordChangeRequest,
    SignInRequest,
    UserCreate,
    UserEnabledUpdate,
    UserRole,
    UserRoleUpdate,
    UserSummary,
)
from mockingbird.security.passwords import WeakPasswordError

if TYPE_CHECKING:
    from fastapi import FastAPI

    from mockingbird.repository.product_repository import ProductRepository

SESSION_COOKIE_NAME = "mb_session"

# --- Role ordering -----------------------------------------------------

_ROLE_RANK: dict[UserRole, int] = {
    UserRole.viewer: 0,
    UserRole.reviewer: 1,
    UserRole.administrator: 2,
}


def role_at_least(role: UserRole, minimum: UserRole) -> bool:
    return _ROLE_RANK[role] >= _ROLE_RANK[minimum]


# --- Cookie helpers ------------------------------------------------------


def _request_is_secure(request: Request) -> bool:
    """Whether this request arrived (or was forwarded) over HTTPS -- a
    `Secure` cookie must never be set for a plain-HTTP LAN deployment (the
    browser would simply refuse to send it back, breaking sign-in
    entirely), but should be set whenever real TLS is in play, including
    behind a documented reverse-proxy deployment (see docs/local-identity-
    multi-user-contract.md "Local network security guidance"). Checking
    `X-Forwarded-Proto` in addition to the direct scheme is a well-
    established, minimal convention for exactly this case; it is trusted
    here only to decide a cookie attribute, never for any authorization
    decision itself.
    """

    if request.url.scheme == "https":
        return True
    return request.headers.get("x-forwarded-proto", "").strip().lower() == "https"


def set_session_cookie(request: Request, response: Response, token: str, *, max_age_seconds: int) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age_seconds,
        path="/",
        httponly=True,
        samesite="lax",
        secure=_request_is_secure(request),
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


# --- Field acceptance bearer-token helpers ---------------------------------
# See docs/non-interactive-field-acceptance-authentication-session-access-
# v1-contract.md. Bearer tokens (not a cookie) are the right transport for
# this identity: its only callers are non-interactive scripts, never a
# browser, so there is no CSRF/Secure/SameSite surface to reuse from the
# human-session mechanism above -- standard `Authorization: Bearer <token>`
# header behavior instead, matching every other bearer-token convention.


def _bearer_token(request: Request) -> str | None:
    """Extract a raw bearer token from `Authorization: Bearer <token>`.
    Never reads a token from a query string or the URL -- see the governing
    contract's "Session/token transport". Returns `None` (never raises) for
    a missing/malformed header."""

    header = request.headers.get("authorization")
    if not header:
        return None
    scheme, _, value = header.partition(" ")
    if scheme.lower() != "bearer" or not value.strip():
        return None
    return value.strip()


def audit_actor(request: Request) -> tuple[str | None, str | None]:
    """Resolve `(actor_user_id, actor_display_name)` for an audit-log entry
    from whichever identity actually authenticated this request -- a
    signed-in human user, or a bearer-token field-acceptance credential
    (never both meaningfully at once; see `_authorize` below for how a
    request can carry either or both). A field-acceptance principal is
    never a `UserModel` row, so `actor_user_id` is always `None` for it --
    `actor_display_name` alone (a distinct, greppable "Field Acceptance
    Operator: ..." prefix) is what lets audit history distinguish its
    actions from a human Administrator's, per the governing contract's
    "Auditability". Returns `(None, None)` if neither identity is present,
    which a handler should treat as "no actor to attribute" rather than
    fail loudly -- audit logging must never itself break a request."""

    current_user = getattr(request.state, "current_user", None)
    if current_user is not None:
        return current_user.id, current_user.display_name
    principal = getattr(request.state, "field_acceptance_principal", None)
    if principal is not None:
        return None, f"Field Acceptance Operator: {principal.label} ({principal.id})"
    return None, None


def current_user_or_401(request: Request) -> CurrentUser:
    """Defense-in-depth: every route that calls this is already gated
    `authenticated`-or-higher by the central policy table below, so
    `request.state.current_user` should always be populated here. This
    exists purely so a future policy-table mistake fails as a clear 401
    rather than an `AttributeError` 500."""

    current_user = getattr(request.state, "current_user", None)
    if current_user is not None:
        return current_user
    raise HTTPException(status_code=401, detail="Sign in to continue.")


def has_administrator_signed_in(request: Request) -> bool:
    current_user = getattr(request.state, "current_user", None)
    return current_user is not None and current_user.role == UserRole.administrator


def setup_mutation_allowed(repository: "ProductRepository", request: Request) -> bool:
    """Shared predicate for the one deliberate exception to the policy
    table below: `/api/setup/state` and `/api/setup/administrator` are
    both tier `public` at the transport gate (a fresh install has no
    signed-in user yet, and the onboarding wizard needs to read/advance
    setup state before that changes), but each still enforces its own
    narrower business rule in-handler once real accounts exist -- see
    docs/local-identity-multi-user-contract.md "First-run administrator".
    Allowed while bootstrap is still open (no enabled Administrator
    exists) for anyone, or afterward for a signed-in Administrator only.
    """

    return not repository.has_eligible_administrator() or has_administrator_signed_in(request)


# --- Error mapping ---------------------------------------------------------

_USER_MUTATION_ERROR_MESSAGES: dict[str, tuple[int, str]] = {
    "login_identity_required": (400, "A login identity is required."),
    "login_identity_already_exists": (409, "That login identity is already in use."),
    "user_not_found": (404, "That user was not found."),
    "cannot_remove_last_administrator": (409, "At least one enabled Administrator must remain."),
    "cannot_disable_last_administrator": (409, "At least one enabled Administrator must remain."),
    "administrator_already_exists": (409, "An Administrator already exists on this Host."),
    "current_password_incorrect": (400, "Current password is incorrect."),
}


def user_mutation_http_error(error: ValueError) -> HTTPException:
    status_code, message = _USER_MUTATION_ERROR_MESSAGES.get(
        str(error), (400, "This request could not be completed.")
    )
    return HTTPException(status_code=status_code, detail=message)


_FIELD_ACCEPTANCE_CREDENTIAL_ERROR_MESSAGES: dict[str, tuple[int, str]] = {
    "field_acceptance_credential_not_found": (404, "That field-acceptance credential was not found."),
}


def field_acceptance_credential_mutation_http_error(error: ValueError) -> HTTPException:
    status_code, message = _FIELD_ACCEPTANCE_CREDENTIAL_ERROR_MESSAGES.get(
        str(error), (400, "This request could not be completed.")
    )
    return HTTPException(status_code=status_code, detail=message)


# --- Routers ---------------------------------------------------------------


def build_auth_router(get_repository: Callable[[], "ProductRepository"]) -> APIRouter:
    """Sign-in/out and self-service account endpoints. Callback-closure
    pattern (a callable rather than a direct import) mirrors `camera_node_
    transport.build_camera_node_transport_router`: `get_repository` is
    defined in `main.py`, below this module in the import graph, so it is
    not available at import time -- only ever called at request time."""

    router = APIRouter(prefix="/api/auth", tags=["auth"])

    @router.post("/sign-in", response_model=CurrentUser)
    async def sign_in(payload: SignInRequest, request: Request, response: Response) -> CurrentUser:
        repository = get_repository()
        # Direct TCP peer address only -- never a forwarded header (see
        # `LoginRateLimiter`'s own module docstring for why). `None` when a
        # test transport carries no real client tuple; `authenticate_user`
        # degrades this to one shared "unknown" source bucket rather than
        # skipping source-keyed throttling entirely.
        source_ip = request.client.host if request.client is not None else None
        result = repository.authenticate_user(payload, source_ip=source_ip)
        if result is None:
            # Deliberately the exact same status/message for every failure
            # reason -- unknown user, wrong password, disabled user, or a
            # currently-throttled account/source (Login Rate-Limiting &
            # Authentication Abuse Resistance v1) -- see `authenticate_
            # user`'s own docstring and docs/local-identity-multi-user-
            # contract.md "Login rate limiting" for the enumeration-safety
            # reasoning.
            raise HTTPException(status_code=401, detail="Incorrect login identity or password.")
        current_user, token = result
        set_session_cookie(
            request, response, token, max_age_seconds=int(repository.SESSION_LIFETIME.total_seconds())
        )
        return current_user

    @router.post("/sign-out", status_code=204)
    async def sign_out(request: Request, response: Response) -> Response:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            get_repository().revoke_session(token)
        clear_session_cookie(response)
        return Response(status_code=204)

    @router.get("/session", response_model=CurrentUser)
    async def get_session(request: Request) -> CurrentUser:
        return current_user_or_401(request)

    @router.post("/change-password", status_code=204)
    async def change_password(payload: SelfPasswordChangeRequest, request: Request) -> Response:
        current_user = current_user_or_401(request)
        token = request.cookies.get(SESSION_COOKIE_NAME)
        try:
            get_repository().change_own_password(current_user.id, payload, current_session_token=token)
        except WeakPasswordError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except ValueError as error:
            raise user_mutation_http_error(error) from error
        return Response(status_code=204)

    return router


def build_admin_users_router(get_repository: Callable[[], "ProductRepository"]) -> APIRouter:
    """Administrator-only user management + audit-log read. Every route
    here is classified `tier administrator` via the `/api/admin/` prefix
    rule in `install_authorization` below, not per-route entries."""

    router = APIRouter(prefix="/api/admin", tags=["admin"])

    @router.get("/users", response_model=list[UserSummary])
    async def list_users() -> list[UserSummary]:
        return get_repository().list_users()

    @router.post("/users", response_model=UserSummary, status_code=201)
    async def create_user(payload: UserCreate, request: Request) -> UserSummary:
        current_user = current_user_or_401(request)
        try:
            return get_repository().create_user(payload, acting_user=current_user)
        except WeakPasswordError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except ValueError as error:
            raise user_mutation_http_error(error) from error

    @router.patch("/users/{user_id}/role", response_model=UserSummary)
    async def update_user_role(user_id: str, payload: UserRoleUpdate, request: Request) -> UserSummary:
        current_user = current_user_or_401(request)
        try:
            return get_repository().update_user_role(user_id, payload, acting_user=current_user)
        except ValueError as error:
            raise user_mutation_http_error(error) from error

    @router.patch("/users/{user_id}/enabled", response_model=UserSummary)
    async def set_user_enabled(user_id: str, payload: UserEnabledUpdate, request: Request) -> UserSummary:
        current_user = current_user_or_401(request)
        try:
            return get_repository().set_user_enabled(user_id, payload, acting_user=current_user)
        except ValueError as error:
            raise user_mutation_http_error(error) from error

    @router.post("/users/{user_id}/reset-password", response_model=UserSummary)
    async def reset_password(
        user_id: str, payload: AdminPasswordResetRequest, request: Request
    ) -> UserSummary:
        current_user = current_user_or_401(request)
        try:
            return get_repository().admin_reset_password(user_id, payload, acting_user=current_user)
        except WeakPasswordError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except ValueError as error:
            raise user_mutation_http_error(error) from error

    @router.get("/audit-log", response_model=list[AuditLogEntry])
    async def get_audit_log(limit: int = 200) -> list[AuditLogEntry]:
        return get_repository().list_audit_log(limit=min(max(limit, 1), 500))

    # No admin-facing GET here: `GET /api/settings/installation` (main.py,
    # deliberately public so a signed-out sign-in screen can show an
    # installation name -- see `_ALWAYS_PUBLIC_PATHS`) already serves the
    # same data; an Administrator reads it the same way everyone else does.
    @router.put("/installation-settings", response_model=InstallationSettings)
    async def update_installation_settings(
        payload: InstallationSettingsUpdate, request: Request
    ) -> InstallationSettings:
        current_user = current_user_or_401(request)
        return get_repository().update_installation_settings(payload, acting_user=current_user)

    return router


def build_admin_field_acceptance_router(get_repository: Callable[[], "ProductRepository"]) -> APIRouter:
    """Provisioning/inspection/revocation for field-acceptance bearer-token
    credentials (Non-Interactive Field Acceptance Authentication & Session
    Access v1; see docs/non-interactive-field-acceptance-authentication-
    session-access-v1-contract.md). Every route here is classified `tier
    administrator` via the pre-existing `/api/admin/` prefix rule in
    `install_authorization` below, not a per-route entry -- this is a
    deliberately Administrator-only surface: the credential this router
    manages can start/stop Observation, so creating or revoking one is
    itself at least as sensitive as the user-management actions the
    sibling `/api/admin/users` router already gates the same way."""

    router = APIRouter(prefix="/api/admin/field-acceptance-credentials", tags=["field-acceptance"])

    @router.post("", response_model=FieldAcceptanceCredentialCreated, status_code=201)
    async def create_field_acceptance_credential(
        payload: FieldAcceptanceCredentialCreate, request: Request
    ) -> FieldAcceptanceCredentialCreated:
        current_user = current_user_or_401(request)
        summary, token = get_repository().create_field_acceptance_credential(
            payload, acting_user=current_user
        )
        return FieldAcceptanceCredentialCreated(**summary.model_dump(), token=token)

    @router.get("", response_model=list[FieldAcceptanceCredentialSummary])
    async def list_field_acceptance_credentials() -> list[FieldAcceptanceCredentialSummary]:
        return get_repository().list_field_acceptance_credentials()

    @router.post("/{credential_id}/revoke", response_model=FieldAcceptanceCredentialSummary)
    async def revoke_field_acceptance_credential(
        credential_id: str, request: Request
    ) -> FieldAcceptanceCredentialSummary:
        current_user = current_user_or_401(request)
        try:
            return get_repository().revoke_field_acceptance_credential(
                credential_id, acting_user=current_user
            )
        except ValueError as error:
            raise field_acceptance_credential_mutation_http_error(error) from error

    return router


# --- Central authorization gate --------------------------------------------


class PolicyTier(str, Enum):
    public = "public"
    authenticated = "authenticated"
    reviewer = "reviewer"
    administrator = "administrator"
    device = "device"


_TIER_MINIMUM_ROLE: dict[PolicyTier, UserRole | None] = {
    PolicyTier.authenticated: None,
    PolicyTier.reviewer: UserRole.reviewer,
    PolicyTier.administrator: UserRole.administrator,
}

# Never gated by a human session at all -- protected by their own device-
# pairing/transport credential instead (see `camera_node_transport.
# require_transport_source`). Human identity and device identity are
# deliberately separate mechanisms (governing milestone brief, "Camera
# Node identity separation") -- this prefix is the *only* place that
# separation is expressed in this module.
DEVICE_PATH_PREFIXES: tuple[str, ...] = ("/api/camera-nodes/transport",)

# Non-Interactive Field Acceptance Authentication & Session Access v1: the
# one, small, explicit set of otherwise-Administrator-tier mutations a valid
# bearer-token field-acceptance credential may also perform -- see
# docs/non-interactive-field-acceptance-authentication-session-access-v1-
# contract.md "Principle of least privilege". Every other `authenticated`
# -tier route (streams, visits, evidence, counterfactual lineage, health,
# and so on) is already reachable by that same credential via the
# `PolicyTier.authenticated` branch below, with no allowlist needed --
# reusing the existing Viewer floor's own read/alert-ack breadth rather
# than building a second, bespoke per-endpoint scoping mechanism (see the
# contract's own "Read scope" for why this is a deliberate, disclosed
# choice, not an oversight). This tuple is deliberately as short as the
# governing brief's own required workflow, not "every operational capture
# control" (`monitor/start`, `live-motion/start`, `audio-capture/start`, and
# similar siblings deliberately stay Administrator-only, unreachable by this
# credential) -- kept as a flat, hand-auditable table, matching `ROUTE_
# POLICY`'s own explicit-over-clever philosophy immediately below.
FIELD_ACCEPTANCE_ALLOWED_ADMIN_ROUTES: frozenset[tuple[str, str]] = frozenset(
    {
        ("POST", "/api/streams/{stream_id}/observation/start"),
        ("POST", "/api/streams/{stream_id}/observation/stop"),
    }
)

# Reachable with no session at all. Kept short and every entry commented:
# each is either needed before any session can exist (setup/sign-in), or
# is deliberately non-sensitive display/build metadata already treated as
# public before this milestone (`/api/product/instance`, `/api/product/
# health` -- version/instance-id strings only, already documented
# elsewhere as non-spoofable-sensitive) or a static asset.
_ALWAYS_PUBLIC_PATHS: frozenset[str] = frozenset(
    {
        "/",
        "/health",
        "/api/setup/state",  # GET always public; PUT self-guards, see setup_mutation_allowed
        "/api/setup/administrator",  # self-guards inside create_first_administrator
        "/api/auth/sign-in",
        "/api/settings/installation",  # GET only in practice (see below); lets a signed-out sign-in screen show an installation name
        "/api/product/instance",
        "/api/product/health",
    }
)


def _is_always_public(path: str) -> bool:
    if path in _ALWAYS_PUBLIC_PATHS:
        return True
    # FastAPI/Starlette's own SPA-serving catch-all and doc routes; never
    # carries API data.
    return path in ("/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect") or not path.startswith(
        "/api/"
    )


# Explicit (method, path template) -> tier overrides. Every entry mirrors
# an exact `@app.<method>("<path>")` declaration in `main.py` -- see
# docs/local-identity-multi-user-contract.md "Authorization" for the
# endpoint-by-endpoint rationale behind each group below. Anything under
# `/api/` not listed here defaults to `authenticated` (the Viewer floor,
# see this module's own docstring) -- never fully open.
ROUTE_POLICY: dict[tuple[str, str], PolicyTier] = {}


def _reviewer(method: str, path: str) -> None:
    ROUTE_POLICY[(method, path)] = PolicyTier.reviewer


def _administrator(method: str, path: str) -> None:
    ROUTE_POLICY[(method, path)] = PolicyTier.administrator


# Reviewer mutations: review/correct/reopen/reject and Visit curation.
for _method, _path in [
    ("POST", "/api/review-labels"),
    ("POST", "/api/visits/{visit_id}/revision"),
    ("POST", "/api/visits/{visit_id}/reopen"),
    ("POST", "/api/review-queue/fast/correct"),
    ("POST", "/api/review-queue/fast/undo"),
    ("POST", "/api/review-queue/bulk-correct"),
    ("POST", "/api/visits/{visit_id}/zone"),
    ("POST", "/api/visits/{visit_id}/split"),
    ("POST", "/api/visits/{visit_id}/merge"),
]:
    _reviewer(_method, _path)

# Administrator mutations: camera/source/stream/zone/yard-map config,
# Camera Node pairing/replacement, storage/retention/backup/recovery,
# species-candidate-pack config, and the review-provenance maintenance
# repair tool (more sensitive than an ordinary correction, so held to the
# higher tier rather than Reviewer).
for _method, _path in [
    ("POST", "/api/review-labels/{review_label_id}/reclassify-provenance"),
    # Camera Node pairing / pending-setup (human-driven via the setup wizard;
    # distinct from the device-credentialed transport router above).
    ("POST", "/api/camera-nodes/pair"),
    ("POST", "/api/camera-nodes/preview"),
    ("POST", "/api/camera-setup/validate"),
    ("PATCH", "/api/camera-nodes/pending-setup/{pairing_token}"),
    ("POST", "/api/camera-nodes/pending-setup/revoke"),
    ("POST", "/api/camera-nodes/pair/revoke"),
    ("POST", "/api/camera-setup/complete"),
    # Source CRUD / provider configuration / ONVIF.
    ("POST", "/api/sources"),
    ("PATCH", "/api/sources/{source_id}"),
    ("PATCH", "/api/sources/{source_id}/provider-configuration"),
    ("POST", "/api/sources/{source_id}/onvif/record-profile"),
    ("POST", "/api/onvif/discover-profiles"),
    ("POST", "/api/sources/{source_id}/webhook/validate"),
    ("POST", "/api/sources/{source_id}/folder-import/preview"),
    ("POST", "/api/sources/{source_id}/folder-import"),
    ("POST", "/api/sources/{source_id}/webhook/motion-evidence"),
    ("POST", "/api/sources/{source_id}/external-url/preview"),
    ("POST", "/api/sources/{source_id}/external-url/preview/save"),
    # Camera configuration edit / reprovision / replace.
    ("POST", "/api/streams/{stream_id}/camera-configuration/preview"),
    ("POST", "/api/streams/{stream_id}/camera-configuration/apply"),
    # Stream configuration.
    ("PUT", "/api/streams/{stream_id}/species-candidate-pack"),
    ("PUT", "/api/streams/{stream_id}/monitoring-policy"),
    ("POST", "/api/streams/{stream_id}/live-motion/settings"),
    # Zone CRUD + monitoring policy (includes Privacy/Ignore zones -- see
    # the governing milestone's "Privacy" section: a Zone's `zone_type` is
    # this product's entire privacy-configuration surface).
    ("POST", "/api/zones"),
    ("PATCH", "/api/zones/{zone_id}"),
    ("DELETE", "/api/zones/{zone_id}"),
    ("PUT", "/api/zones/{zone_id}/monitoring-policy"),
    ("POST", "/api/zones/{zone_id}/monitoring-policy/restore-defaults"),
    # Yard Map spatial configuration.
    ("POST", "/api/yard-map/blank"),
    ("PATCH", "/api/yard-map"),
    ("POST", "/api/yard-map/background"),
    ("DELETE", "/api/yard-map/background"),
    ("PUT", "/api/yard-map/streams/{stream_id}"),
    ("DELETE", "/api/yard-map/streams/{stream_id}"),
    ("PUT", "/api/yard-map/zones/{zone_id}"),
    ("DELETE", "/api/yard-map/zones/{zone_id}"),
    # Storage / retention / backup / recovery.
    ("PUT", "/api/settings/storage-retention"),
    ("POST", "/api/settings/storage-retention/cleanup-preview"),
    ("POST", "/api/settings/storage-retention/cleanup"),
    ("POST", "/api/settings/storage-retention/cleanup-history/{batch_id}/restore"),
    ("POST", "/api/settings/storage-retention/cleanup-history/{batch_id}/purge"),
    ("POST", "/api/settings/backups"),
    ("POST", "/api/settings/backups/import"),
    ("POST", "/api/settings/backups/{backup_id}/verify"),
    ("POST", "/api/settings/backups/{backup_id}/restore-plan"),
    ("POST", "/api/settings/backups/{backup_id}/restore"),
    ("POST", "/api/settings/reset-demo-data"),
    ("POST", "/api/settings/remove-sample-data"),
    # (installation settings write lives at PUT /api/admin/installation-settings,
    # already covered by the /api/admin/ prefix rule below)
    # Species candidate packs (detection/suggestion system configuration).
    ("POST", "/api/species-candidate-packs"),
    ("PUT", "/api/species-candidate-packs/{pack_id}"),
    ("POST", "/api/species-candidate-packs/{pack_id}/clone"),
    ("POST", "/api/species-candidate-packs/{pack_id}/archive"),
    # Operational capture controls: arming/disarming a detection pipeline
    # has real recording/resource/privacy consequences, so it is bundled
    # with camera/system configuration rather than left at the Viewer
    # floor.
    ("POST", "/api/streams/{stream_id}/monitor/start"),
    ("POST", "/api/streams/{stream_id}/monitor/stop"),
    ("POST", "/api/streams/{stream_id}/runtime/retry"),
    ("POST", "/api/streams/{stream_id}/live-motion/start"),
    ("POST", "/api/streams/{stream_id}/live-motion/stop"),
    ("POST", "/api/streams/{stream_id}/observation/start"),
    ("POST", "/api/streams/{stream_id}/observation/stop"),
    ("POST", "/api/streams/{stream_id}/audio-capture/start"),
    ("POST", "/api/streams/{stream_id}/audio-capture/stop"),
]:
    _administrator(_method, _path)


def _match_route(request: Request):
    """Resolve which registered route this request would actually
    dispatch to, using Starlette's own matcher (`Route.matches`) rather
    than re-deriving path-template logic -- confirmed empirically against
    this project's installed Starlette version to be available and
    correct *before* `call_next` (i.e. before routing itself has run;
    `request.scope["route"]` is not yet populated at this point, only
    `route.matches()` called directly against each candidate is)."""

    scope = dict(request.scope)
    for route in request.app.router.routes:
        match, _child_scope = route.matches(scope)
        if match == Match.FULL:
            return route
    return None


def _resolve_tier(request: Request) -> PolicyTier:
    path = request.url.path
    if _is_always_public(path):
        return PolicyTier.public
    if any(path.startswith(prefix) for prefix in DEVICE_PATH_PREFIXES):
        return PolicyTier.device
    # New user-management/audit surface is entirely under this one prefix
    # (see `build_admin_users_router`) -- a prefix rule here is exactly as
    # auditable as a per-route entry (every route under it really is
    # Administrator-only) without needing one line per endpoint.
    if path.startswith("/api/admin/"):
        return PolicyTier.administrator
    route = _match_route(request)
    if route is not None:
        override = ROUTE_POLICY.get((request.method, getattr(route, "path", "")))
        if override is not None:
            return override
    # Safe default for everything else under /api/: any signed-in enabled
    # user, never fully open.
    return PolicyTier.authenticated


def _matches_field_acceptance_allowlist(request: Request) -> bool:
    """Whether this request's *actual dispatch route* (via the same real
    `Route.matches` resolution `_resolve_tier` already used, never a raw
    `request.url.path` string compare) is one of the small, explicit
    `FIELD_ACCEPTANCE_ALLOWED_ADMIN_ROUTES` entries a field-acceptance
    credential may perform despite otherwise needing Administrator."""

    route = _match_route(request)
    path = getattr(route, "path", "") if route is not None else ""
    return (request.method, path) in FIELD_ACCEPTANCE_ALLOWED_ADMIN_ROUTES


def _deny(status_code: int, message: str) -> JSONResponse:
    # Matches the universal `{"detail": "..."}` shape every existing
    # `HTTPException(detail=...)` produces (see docs/local-identity-multi-
    # user-contract.md "Authorization") -- the frontend's existing error
    # parsing needs no changes to understand this. Built as a plain
    # JSONResponse, not a raised HTTPException: this code runs inside
    # `@app.middleware("http")`'s "before" phase, which sits *outside*
    # FastAPI's own `ExceptionMiddleware` layer (confirmed empirically) --
    # an `HTTPException` raised here would propagate as an unhandled 500
    # instead of the intended 401/403.
    return JSONResponse(status_code=status_code, content={"detail": message})


def install_authorization(app: "FastAPI", *, get_repository: Callable[[], "ProductRepository"]) -> None:
    """Install the one central `@app.middleware("http")` authorization
    gate. Must be called after every route (including `app.include_
    router(...)` calls) is registered -- `_match_route` reads `request.
    app.router.routes` fresh on every request, so route *registration*
    order relative to this call does not itself matter, but this is kept
    at the very end of `main.py` regardless, so the policy table above and
    the actual route list it is checked against are always visibly next
    to each other in review."""

    @app.middleware("http")
    async def _authorize(request: Request, call_next):  # noqa: ANN001, ANN201 - Starlette's own untyped middleware signature
        current_user: CurrentUser | None = None
        token = request.cookies.get(SESSION_COOKIE_NAME)
        if token:
            current_user = get_repository().resolve_session(token)
        request.state.current_user = current_user

        # Non-Interactive Field Acceptance Authentication & Session Access
        # v1: resolved independently of, and never merged into, `current_
        # user` above -- a field-acceptance credential is deliberately not
        # a `UserModel`/`CurrentUser` identity (see `FieldAcceptanceCredent
        # ialModel`'s own docstring). Resolving it unconditionally (not only
        # when no cookie session was found) keeps the two identities fully
        # independent, so a request carrying both is judged on whichever
        # one actually satisfies the tier below, never on which was checked
        # first.
        field_acceptance_principal: FieldAcceptancePrincipal | None = None
        bearer_token = _bearer_token(request)
        if bearer_token:
            field_acceptance_principal = get_repository().resolve_field_acceptance_token(bearer_token)
        request.state.field_acceptance_principal = field_acceptance_principal

        tier = _resolve_tier(request)
        if tier in (PolicyTier.public, PolicyTier.device):
            return await call_next(request)

        if tier == PolicyTier.authenticated:
            # The Viewer floor: reachable by a signed-in human of any role,
            # or by a valid field-acceptance credential -- see `FIELD_
            # ACCEPTANCE_ALLOWED_ADMIN_ROUTES`'s own docstring for why this
            # credential's read scope is deliberately the existing Viewer
            # floor rather than a narrower bespoke allowlist.
            if current_user is not None or field_acceptance_principal is not None:
                return await call_next(request)
            return _deny(401, "Sign in to continue.")

        minimum_role = _TIER_MINIMUM_ROLE[tier]
        if current_user is not None and role_at_least(current_user.role, minimum_role):
            return await call_next(request)
        if (
            tier == PolicyTier.administrator
            and field_acceptance_principal is not None
            and _matches_field_acceptance_allowlist(request)
        ):
            return await call_next(request)
        if current_user is None and field_acceptance_principal is None:
            return _deny(401, "Sign in to continue.")
        return _deny(403, f"This action requires {minimum_role.value.capitalize()} access.")
