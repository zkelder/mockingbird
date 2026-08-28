# Non-Interactive Field Acceptance Authentication & Session Access v1 contract

Status: a bounded, release-critical security/correctness dependency
milestone -- not a product capability, not a broader auth redesign. Schema
57 -> 58. See
[local-identity-multi-user-contract.md](local-identity-multi-user-contract.md)
for the authentication/authorization architecture this milestone extends;
this document only covers the delta.

## Problem

Three consecutive Representative Field Acceptance / Gate A attempts
(2026-08-25, 2026-08-26, 2026-08-28; see
[representative-daylight-field-acceptance-gate-a-evidence-v2-report.md](representative-daylight-field-acceptance-gate-a-evidence-v2-report.md))
found the same blocker: the real local product, correctly, requires a
signed-in session for every endpoint a field-acceptance session needs
(Streams, Observation start/stop, Visits, counterfactual/admission
lineage). That requirement is itself correct and intentional -- it is
exactly what [[local-identity-multi-user-contract.md]] shipped
(2026-08-23), and it must not be weakened. What was missing was a
*supported way for bounded, non-interactive tooling to authenticate*
without sharing the operator's personal Administrator password, without a
localhost/header bypass, and without disabling authentication.

No existing mechanism was available to reuse: this codebase's only
identity systems before this milestone were (1) human `UserModel` accounts
on the Viewer < Reviewer < Administrator ladder, cookie-session
authenticated, and (2) Camera Node device pairing/transport credentials,
structurally unrelated to human identity. Neither fits a non-interactive
script.

## Chosen mechanism (Option B: explicit local acceptance principal)

A new, narrow, bearer-token-authenticated credential: **Field Acceptance
Operator**. Deliberately a **second, parallel identity system**, mirroring
this codebase's own existing precedent for exactly this shape -- Camera
Node device identity is already completely separate from human `UserModel`
identity (see [[local-identity-multi-user-contract.md]] "Camera Node
identity separation"). This is not a fourth value on the Viewer/Reviewer/
Administrator role ladder: that ladder is strictly linear
(`role_at_least`), and the required permission shape here -- broad
Viewer-level reads, plus exactly two otherwise-Administrator-tier
mutations (Observation start/stop) and nothing else Administrator-tier --
is not a contiguous prefix of that ladder. No single rank placement could
express it without either under- or over-granting (see
`FieldAcceptanceCredentialModel`'s own docstring in
`src/mockingbird/storage/models.py` for the full reasoning). A parallel
identity, checked by the same central gate, was the smallest correct
extension -- not a new RBAC framework.

Bearer-token transport (`Authorization: Bearer <token>`), not a cookie
session: this credential's only caller is non-interactive tooling, never a
browser, so there is no CSRF/Secure/SameSite surface to reuse from the
human-session mechanism, and standard bearer-token header behavior is the
right fit.

## Data model (schema 58)

One new, purely additive table, `field_acceptance_credentials`
(`FieldAcceptanceCredentialModel`, `src/mockingbird/storage/models.py`):

| Column | Notes |
|---|---|
| `id` | `field-acceptance-<16 hex>` |
| `label` | operator-chosen, default `"Field Acceptance Operator"` |
| `token_hash` | `hashlib.sha256(token).hexdigest()` -- only the hash is ever persisted, via the exact same `generate_session_token`/`hash_session_token` helpers (`mockingbird.security.passwords`) sessions already use. A stolen database backup cannot be replayed as a live credential. |
| `created_at` | |
| `created_by_user_id` / `created_by_display_name` | the provisioning Administrator, point-in-time snapshot (mirrors `AuditLogEntryModel.actor_user_id`/`.actor_display_name`) |
| `expires_at` | **not nullable** -- every credential is bounded by construction; there is no "permanent" path in v1 at all (deliberately stricter than the governing brief's own minimum bar of "not the *only* path") |
| `revoked_at` | `NULL` = never revoked, mirrors `UserSessionModel.revoked_at`'s exact "honest absence" convention |
| `last_used_at` | updated unconditionally on every successful resolution (not throttled the way session renewal is -- field-acceptance call volume is orders of magnitude below an interactive browser session's) |

Migration `_migrate_to_field_acceptance_authentication`
(`src/mockingbird/storage/database.py`) creates this one table, nothing
else; nothing is backfilled -- an upgraded installation starts with zero
credentials, matching "not created automatically on normal installs."

## Principle of least privilege

The credential's read scope is deliberately the **existing Viewer floor**
(every `authenticated`-tier `GET`, plus the personal alert-acknowledge
toggle) -- not a bespoke, narrower, per-endpoint read allowlist. This is a
disclosed, deliberate choice: Viewer is already this product's own
legitimate low-privilege read role, and building a second, bespoke
read-scoping mechanism purely for this one credential would itself be the
"sprawling new RBAC framework" the governing brief says to avoid. The
credential can never reach a `reviewer`- or `administrator`-tier route
through this path -- only the small, explicit exception below.

The one Administrator-tier exception,
`FIELD_ACCEPTANCE_ALLOWED_ADMIN_ROUTES` (`src/mockingbird/api/auth.py`), is
a flat, hand-auditable two-entry table:

```python
{
    ("POST", "/api/streams/{stream_id}/observation/start"),
    ("POST", "/api/streams/{stream_id}/observation/stop"),
}
```

Deliberately **not** every "operational capture control" -- `monitor/
start`, `live-motion/start`, `audio-capture/start`, and their `stop`
siblings stay Administrator-only, unreachable by this credential, because
the governing brief's required workflow names only Observation start/stop.

### Endpoint/permission matrix (the live acceptance workflow)

| Capability | Tier | Reachable by this credential? |
|---|---|---|
| List/read Streams (`GET /api/streams`) | authenticated | Yes |
| Start Observation (`POST .../observation/start`) | administrator | Yes (explicit allowlist) |
| Stop Observation (`POST .../observation/stop`) | administrator | Yes (explicit allowlist) |
| Read Visits (`GET /api/visits`) | authenticated | Yes |
| Read Visit/Event evidence | authenticated | Yes |
| Read health (`GET /api/product/health`) | public | Yes (no credential even needed) |
| Read counterfactual/admission lineage (`GET .../observation/counterfactual`) | authenticated | Yes |
| Read Observation status/coverage (`GET .../observation/status`) | authenticated | Yes |
| Create/delete human users, promote roles | administrator (`/api/admin/*`) | **No** -- 403 |
| Change Administrator credentials | administrator (`/api/admin/*`) | **No** -- 403 |
| Change security/installation settings | administrator | **No** -- 403 |
| Create/revoke a field-acceptance credential | administrator (`/api/admin/field-acceptance-credentials`) | **No** -- 403 (cannot mint or revoke its own or any other credential) |
| Camera/Source/Zone configuration, backups, species packs | administrator | **No** -- 403 |
| `monitor/start`, `live-motion/start`, `audio-capture/start` and their `stop` siblings | administrator | **No** -- 403 (deliberately outside the narrow allowlist) |
| Review/correct/reopen a Visit | reviewer | **No** -- 403 |

## Provisioning

`scripts/manage_field_acceptance_credential.py` -- a bounded administrative
command mirroring the existing `scripts/repair_review_label_provenance.py`
precedent: talks to a *running* instance over its real HTTP API (never
opens the SQLite file directly), authenticated as an **already-existing**
local Administrator (`POST /api/auth/sign-in`, exactly the product's own
sign-in flow). It cannot bootstrap the first Administrator -- provisioning
always requires prior local administrative authority, never a default
account. Subcommands:

```bash
python scripts/manage_field_acceptance_credential.py create [--label TEXT] [--ttl-hours N]
python scripts/manage_field_acceptance_credential.py list
python scripts/manage_field_acceptance_credential.py revoke --credential-id <id>
```

The Administrator password used for provisioning is **never** a
command-line argument (shell-history/process-argument exposure) -- only an
unechoed `getpass` prompt or the `MOCKINGBIRD_ADMIN_PASSWORD` environment
variable. The minted bearer token is printed exactly once, to stdout only,
by `create`; `list`/`revoke` never print a secret.

Server-side (`build_admin_field_acceptance_router`,
`src/mockingbird/api/auth.py`): `POST /api/admin/field-acceptance-
credentials`, `GET /api/admin/field-acceptance-credentials`, `POST
/api/admin/field-acceptance-credentials/{id}/revoke` -- all three
automatically Administrator-tier through the pre-existing `/api/admin/`
prefix rule already in `install_authorization` (no new `ROUTE_POLICY`
entries needed for provisioning itself).

## Credential lifecycle

- **Create**: explicit, Administrator-only, `expires_in_hours` bounded
  `1..720` (30 days) by the request schema, default 24.
- **Inspect**: `GET /api/admin/field-acceptance-credentials` returns `id`,
  `label`, `created_at`, `created_by_user_id`/`created_by_display_name`,
  `expires_at`, `revoked_at`, `last_used_at` -- never the token or its
  hash.
- **Revoke**: `POST .../{id}/revoke`, immediate and deterministic.
  `resolve_field_acceptance_token` re-reads `revoked_at` fresh from the row
  on *every* call (no cache, no blocklist sweep) -- exactly
  `resolve_session`'s own contract -- so the very next authentication
  attempt with that token fails. Idempotent: revoking an already-revoked
  credential returns it unchanged rather than raising.
- **Rotate**: not implemented as a distinct operation in v1 -- explicit
  revoke + `create` again is the supported path, per the governing brief's
  own allowance ("If rotation would meaningfully expand scope, explicit
  revoke+recreate is acceptable for v1").
- **Expire**: mandatory, not optional -- there is no permanent-credential
  path in this table at all (see "Data model" above). A server restart
  cannot resurrect an expired *or* revoked credential: both facts live only
  in this one row, re-read fresh on every resolution, with nothing cached
  in memory across a process lifetime.

## Auditability

Reuses the existing `AuditLogEntryModel`/`record_audit_event` mechanism
unmodified -- no new audit subsystem. New actions:
`field_acceptance_credential.created`, `field_acceptance_credential.
revoked` (actor = the provisioning/revoking Administrator, `metadata` =
`{"label": ...}`, never the token); `stream.observation_started`,
`stream.observation_stopped` (actor = whichever identity actually
authenticated the request -- a human Administrator, or this credential).

A field-acceptance principal is never a `UserModel` row, so its
`actor_user_id` is always `NULL` in an audit entry it caused;
`actor_display_name` instead carries a distinct, greppable
`"Field Acceptance Operator: <label> (<credential id>)"` prefix
(`mockingbird.api.auth.audit_actor`) -- exactly what lets audit history
distinguish its actions from a human Administrator's, per the governing
brief's requirement.

Observation start/stop were **not previously audited at all** for a human
Administrator either (this codebase's existing audit-action taxonomy
covered user/review/camera/privacy/retention/backup/installation actions,
but not arming/disarming a capture pipeline). This milestone closes that
pre-existing gap for both callers as one small, additive, unconditional
change (`_observation_action_response`, `src/mockingbird/api/main.py`) --
not scope creep, since it is exactly the auditability this credential's own
one allowed mutation requires, and it was cheaper and more honest to fix
once for both identities than to special-case logging only for the new
one.

## Security properties / no-bypass

- No auth bypass: the credential is checked by the exact same central
  `install_authorization` `@app.middleware("http")` gate every other
  request already passes through -- no parallel/insecure auth stack.
- No localhost/IP-based trust: nothing about this mechanism treats
  `127.0.0.1` as itself a credential.
- No debug header, no query-string token, no cookie-value token --
  `Authorization: Bearer <token>` only.
- A signed-in low-privilege human session (Viewer) and a valid
  field-acceptance bearer token presented together cannot combine into
  more privilege than either grants alone (each tier check considers both
  identities independently; see `mockingbird.api.auth._authorize`).
- Storage: hash-only (SHA-256, matching session-token conventions), never
  plaintext at rest.
- Logging: the raw token is never logged anywhere in the product or in
  `scripts/manage_field_acceptance_credential.py`/`scripts/field_
  acceptance_client.py`. The existing support-bundle credential-shaped
  denylist (`"token"`, `"bearer"`, `"secret"`, ...;
  `mockingbird.diagnostics.support_bundle._CREDENTIAL_SHAPED_SUBSTRINGS`)
  already covers this vocabulary unmodified.
- Replay: a bearer token is a static secret for its lifetime (like any
  bearer token) -- mitigated by the mandatory bounded expiry, explicit
  revocation, and hash-only storage above. No hardware-backed key
  infrastructure was built for v1, matching the governing brief's explicit
  bound ("Do not turn v1 into hardware-backed key infrastructure").
- CSRF: the credential is never cookie-based, so it carries no CSRF
  surface of its own; the existing `SameSite=Lax` human-session CSRF
  posture is unchanged.

See `tests/test_field_acceptance_authentication.py` for the full regression
suite proving each of these directly over real HTTP.

## Tooling integration

`scripts/field_acceptance_client.py` -- a small, stdlib-only
(`urllib`) HTTP client reading `MOCKINGBIRD_ACCEPTANCE_TOKEN` from the
environment and attaching it as `Authorization: Bearer <token>` on every
call. No dedicated wrapper for this HTTP sequence existed before this
milestone (every prior field-acceptance report documented the exact manual
`curl`/REST sequence instead); this is deliberately *not* a full
field-session launcher (no tmux orchestration, no acceptance-recorder
wiring, no post-session accounting) -- that broader, separately-named gap
stays out of scope, exactly as the prior report that first named it
recommended.

Covers exactly the governing brief's named workflow: `list_streams`,
`list_visits`, `start_observation`, `stop_observation`,
`observation_status`, `observation_counterfactual`, `product_health`.
Fails clearly and distinctly for every required case:

| Condition | Result |
|---|---|
| `MOCKINGBIRD_ACCEPTANCE_TOKEN` unset | `FieldAcceptanceCredentialMissingError`, raised before any request |
| Server returns 401 (unknown/malformed/expired/revoked token -- deliberately indistinguishable at this layer, matching `resolve_session`'s own non-disclosure convention) | `FieldAcceptanceCredentialInvalidError` |
| Server returns 403 (authenticated, insufficient scope) | `FieldAcceptancePermissionError` |
| Any other non-2xx | `FieldAcceptanceApiError` |

No anonymous fallback anywhere in this client.

## Documentation cross-references

- [local-identity-multi-user-contract.md](local-identity-multi-user-contract.md)
  -- the authentication/authorization architecture this milestone extends.
- [non-interactive-field-acceptance-authentication-session-access-v1-report.md](non-interactive-field-acceptance-authentication-session-access-v1-report.md)
  -- this milestone's own execution report (real acceptance proof,
  validation results, classification).

## What this deliberately does not do

No authentication bypass; no anonymous local endpoints; no magic debug
header; no broad RBAC redesign; no OAuth/OIDC/SSO; no cloud identity; no
enterprise service-account management; no fleet credential management; no
frontend account-management UI (CLI/admin tooling is sufficient for v1,
per the governing brief's explicit scope); no hardware-backed key
infrastructure; no change to first-run Administrator bootstrap.
