# Local Identity, Multi-User & Organization Access v1 contract

Status: "Remaining roadmap -- canonical sequence" Layer 1
(see [roadmap.md](roadmap.md)) -- the first milestone after the
2026-08-23 ecosystem-observatory reconciliation. Makes one authoritative
local MockingBird Host safely usable by multiple people from multiple
workstations, without cloud tenancy, per-workstation databases, or a
second truth system. Schema 49 -> 50.

## Boundary

This is Multi-User, not Multi-Site. One Host remains one deployment/
security boundary that owns observations, reviewed truth, evidence,
camera/source configuration, storage/recovery, privacy, and organizational
policy -- multi-user adds *who is allowed to act on that one Host's truth*,
not a second Host, a second database, or a second truth system. It does
**not** build LDAP, Active Directory, OIDC, SAML, SCIM, SaaS tenancy,
Multi-Site, an `Organization` tenancy hierarchy, mobile/PWA, or ACME/PKI
infrastructure -- see "Explicit exclusions" below and "Deployment and
organization doctrine" in [product-doctrine.md](product-doctrine.md),
which already named this exact boundary before this milestone existed.

Canonical topology:

```
Camera Nodes  ->  authoritative local MockingBird Host  <-  many authenticated browsers/PWA clients
```

Camera Nodes authenticate as devices (an existing, separate mechanism --
see "Camera Node identity separation" below); humans authenticate
separately as users. Nothing about Camera Node pairing/replacement
changes here.

## Identity model

`UserModel` (`users` table) is the first identity/account table this
product has ever had: `id`, `display_name`, `login_identity` (a local
username, stored lowercase-normalized; not necessarily an email),
`password_hash`, `role`, `enabled`, `created_at`/`updated_at`, and
`password_updated_at` (informational only -- see "Sessions" below for why
it is deliberately *not* cross-checked against session age).

Roles are a deliberately small ladder, `mockingbird.api.auth.role_at_least`
(Viewer < Reviewer < Administrator):

- **Viewer** -- view Today/history/Place/Bird Log, inspect evidence, view
  reports, view camera/source health. Cannot mutate reviewed truth or
  system configuration.
- **Reviewer** -- Viewer, plus confirm/correct/reject/reopen where existing
  semantics permit, and review inferred wildlife/habitat intelligence as
  those domains are added.
- **Administrator** -- Reviewer, plus camera/source management, privacy,
  retention/storage, backup/recovery, user management, and system
  configuration.

No distinct Owner role: nothing in this milestone's destructive-recovery
semantics needed one. No fine-grained enterprise RBAC -- three roles cover
every distinction the acceptance journeys require.

Passwords are hashed with the Python standard library's `hashlib.scrypt`
(RFC 7914) -- see `mockingbird.security.passwords`'s own module docstring
for why stdlib rather than a third-party dependency (`bcrypt`/`argon2-cffi`/
`passlib` are all uninstalled, and this project has repeatedly hit real,
costly compiled-wheel problems on its packaged Windows build). Never
plaintext, never reversible; the stored string is self-describing
(`scrypt$n=..,r=..,p=..$<salt>$<hash>`) so a future cost-parameter change
can recognize and transparently re-hash an old-format row on its next
successful login (`needs_rehash`). Minimum password length 10 characters,
matching NIST SP 800-63B's length-over-composition-rules guidance -- no
uppercase/digit/symbol requirements.

## First-run administrator bootstrap

`ProductRepository.has_eligible_administrator()` -- "does at least one
enabled Administrator currently exist" -- re-evaluated live on every call,
never a one-shot flag. `create_first_administrator` refuses
(`administrator_already_exists`) whenever that is true, guarded by
`_administrator_bootstrap_lock`, the same coarse in-process
critical-section pattern `ProductRepository._observation_authority_lock`
already established for this exact class of problem (correct for this
product's single-process local-first runtime; not a claim of cross-process
safety -- see that lock's own docstring). No default `admin`/`admin`, no
hidden seeded credential: `users` starts genuinely empty on a fresh
install, and `create_first_administrator` is the only way to populate it.

The onboarding wizard (`web/src/components/OnboardingWizard.tsx`) gained
one new step, `"account"`, inserted between the pre-existing `"welcome"`
and `"storage"` steps -- every later step needs a real signed-in session
(the safe `authenticated` default described below), so account creation
has to come before the first one that reads real data. On success the
backend both creates the Administrator and sets the session cookie, so the
wizard continues straight into storage/camera/observe fully authenticated
with no separate sign-in step. `PUT /api/setup/state` and
`POST /api/setup/administrator` are both transport-tier `public` (a fresh
install has no signed-in user yet), but each enforces its own narrower
rule in-handler via `setup_mutation_allowed`: allowed while bootstrap is
still open, or afterward for a signed-in Administrator only -- the one
deliberate exception to the central policy table, chosen because the
business rule ("no admin yet, or you are one") cannot be expressed as a
static per-route tier.

Reused rather than reinvented: this is "If clean-install/onboarding
already provides an appropriate setup boundary, extend it rather than
creating a separate setup application," applied literally.

## Authentication (sessions)

`UserSessionModel` (`user_sessions`) is deliberately opaque and
server-side rather than a self-contained token like a JWT: the browser
cookie (`mb_session`, `HttpOnly`, `SameSite=Lax`) carries only a
high-entropy random token (`secrets.token_urlsafe(32)`); only its SHA-256
hash is ever persisted (a stolen database backup cannot be replayed as a
live session). `resolve_session` re-reads the live `UserModel` row --
`.enabled`/`.role` -- on every single call, which is what lets a disable
or role change take effect on the very next request with no separate
revocation/blocklist sweep.

`Secure` is set dynamically per request (`request.url.scheme == "https"`
or a trusted `X-Forwarded-Proto: https`), never hardcoded -- a plain-HTTP
LAN deployment must not have its cookie silently refused, but a real
reverse-proxy TLS deployment should get it. See "Local network security
guidance" below.

Session lifetime is a plain 30-day rolling window (`ProductRepository.
SESSION_LIFETIME`), renewed (throttled to once per hour of use) rather
than re-issued on every request -- deliberately simple for a local
appliance-class product, not a claim this is the only reasonable choice.

Revocation is always explicit, never inferred from a timestamp
comparison:

- **Sign-out** revokes exactly that one session.
- **Admin password reset** (`admin_reset_password`) revokes every session
  the target user has.
- **Self-service password change** (`change_own_password`) revokes every
  *other* session but deliberately preserves the one making the request --
  it already just proved itself with the correct current password, so
  forcing an immediate re-sign-in would be friction without a security
  benefit. `resolve_session` does **not** also compare `password_updated_
  at` against a session's `created_at` as a second, independent staleness
  check -- doing so would silently re-invalidate exactly the session this
  exemption preserves. See `resolve_session`'s own docstring for the full
  reasoning (found by direct test execution, not designed defensively
  up front).
- **Disabling a user** needs no explicit session revocation at all: the
  live `.enabled` check in `resolve_session` already covers it on the very
  next request.

## Server-side authorization

`mockingbird.api.auth.install_authorization` is the one central
`@app.middleware("http")` gate every request passes through -- mirroring
this codebase's own established idiom (`Depends()` is never used anywhere
in the 271 pre-existing endpoints; the existing request-correlation-id
middleware is the closer precedent). It resolves the caller's identity
once and stores it on `request.state.current_user`, exactly like
`request.state.request_id` already works; a handler that needs the
caller's identity for review attribution or audit logging just takes
`request: Request` and calls `current_user_or_401(request)`.

`ROUTE_POLICY` is a flat, explicit, hand-written `(method, path template)
-> tier` mapping, not a regex/prefix scheme generated from route
introspection -- given the security stakes, an explicit table a reviewer
can read top to bottom was judged worth more than a cleverer mechanism.
Matching an *incoming* request against it still reuses Starlette's own
real route matcher (`Route.matches`, confirmed empirically against this
project's installed Starlette version, including that `request.scope
["route"]` is *not* populated before `call_next` -- only calling `route.
matches()` directly is) rather than a hand-rolled path-template parser, so
there is no risk of the gate's idea of "which route is this" ever
diverging from what the router itself would actually dispatch to.

Tiers: `public` (no session needed), `device` (Camera Node's own
pairing/transport credential -- see "Camera Node identity separation"),
`authenticated` (any signed-in enabled user -- the Viewer floor),
`reviewer`, `administrator`. **Every `/api/*` path defaults to
`authenticated` unless explicitly listed otherwise** -- a mutation
endpoint accidentally left out of the `reviewer`/`administrator` tables is
never fully open; at worst it is reachable by a signed-in Viewer, never by
an unauthenticated caller. This default was verified against the live app
object (every `ROUTE_POLICY` entry cross-checked against `app.router.
routes`, and representative tier resolutions spot-checked) before relying
on it.

Endpoint classification (see `ROUTE_POLICY` in `mockingbird/api/auth.py`
for the exhaustive list):

- **Reviewer**: `POST /api/review-labels`, `/visits/{id}/revision`,
  `/reopen`, `/zone`, `/split`, `/merge`; `POST /api/review-queue/fast/
  correct`, `/undo`, `/bulk-correct`.
- **Administrator**: all camera/source/stream/zone/yard-map configuration
  mutations (Zone `zone_type` is this product's entire privacy-mask
  surface -- privacy is not a separate endpoint family); Camera Node
  pairing/pending-setup/revoke (human-driven via the setup wizard --
  distinct from the device-credentialed transport router); storage
  retention/cleanup, backup create/import/verify/restore; species
  candidate packs; operational capture controls (stream/live-motion/
  observation/audio-capture start-stop -- arming a detection pipeline has
  real recording/resource/privacy consequences, so it is bundled with
  configuration rather than left at the Viewer floor); the review-
  provenance maintenance repair tool; everything under `/api/admin/`
  (user management, audit log, installation settings) via one prefix
  rule.
- **Authenticated (Viewer floor, the safe default)**: live camera
  viewing/preview (`live-session`, `live-preview`, `camera-controls/open`
  -- "watching" is Viewer-safe, matches "inspect evidence"), alert
  acknowledge/dismiss (a personal read-state toggle, not a system
  mutation), and every other read.
- **Public**: `/`, `/health`, static assets, `GET /api/setup/state`,
  `POST /api/setup/administrator` (self-guarding, see above),
  `POST /api/auth/sign-in`, `GET /api/settings/installation` (lets a
  signed-out sign-in screen show an installation name -- display metadata
  only, never anything sensitive), `GET /api/product/instance`/`/health`
  (already-documented non-sensitive version/instance-id strings).
- **Device**: the `camera_node_transport` router only -- protected by its
  own pairing/transport credential, never a human session.

Hiding a frontend button is not authorization: `web/src/App.tsx` filters
its nav list by role (`minRole` per item) for calm UX, but that filtering
is redundant with, never a substitute for, the server-side gate above --
proven directly (Journey 2/3/12) by signing in as each role over real HTTP
and confirming the server itself rejects an out-of-role mutation.

## Review attribution

`ReviewLabelModel.reviewed_by_user_id` (nullable, `ForeignKey("users.
id")`) is the new, durable, unspoofable actor reference -- populated
unconditionally from the real signed-in `acting_user` wherever a review
handler has one (`create_review_label`, `revise_visit_review`,
`reopen_visit_review`, `bulk_correct_review_queue_items`,
`create_fast_review_correction`, and the reversal row `undo_fast_review_
correction` writes), and `NULL` for every row from before this milestone,
or from any offline/CLI/demo-seed/non-interactive caller that never passes
`acting_user` at all (the parameter defaults to `None`, preserving those
call sites' exact pre-existing behavior with zero changes).

Deliberately does **not** also force-override `review_origin`/
`reviewer_identity`: the product's own interactive review UI already
stamps `review_origin: "human"` itself at the single API client boundary
(`web/src/api/client.ts`'s `createReviewLabel`/`reviseVisitReview`/etc.),
confirmed directly rather than assumed -- so a signed-in `acting_user`
touching that field too would have been a second, redundant, and riskier
mechanism (verified by direct execution that it would have silently
corrupted the pre-existing `agent_diagnostic`/`imported_curated`/omitted-
origin provenance contract multiple existing tests depend on). Instead,
`_reviewer_identity_with_signed_in_default` fills a *blank*
`reviewer_identity` from the signed-in user's display name, but only for
an explicitly `"human"`-origin request -- never for any other origin
(including a merely-omitted one), and never overriding a value the client
did supply. Confirmed via direct audit of the existing test suite that no
test asserts `reviewer_identity` stays blank for that exact case before
relying on this.

`POST /api/review-labels`'s `ReviewCorrectionCreate.expected_state_token`
is a new, optional field reusing the exact `_review_state_token`/
`ReviewRevisionConflictError` mechanism `/revision`/`/reopen`/Fast Review
already had (see "Optimistic concurrency" below) -- optional so every
non-interactive caller that omits it keeps today's exact last-write-wins
behavior; the interactive frontend always supplies it.

## Optimistic concurrency

Reused an existing mechanism rather than inventing one: `_review_state_
token` (a bounded sha256 digest of target type/id/review_status/
reviewed_label/latest_review_label_id/curation_state) already existed and
was already enforced by `/visits/{id}/revision`, `/reopen`, and the Fast
Review endpoints, fully tested by `tests/test_reviewed_observation_
revision.py` before this milestone. The one real gap
(`POST /api/review-labels`, the initial confirm/correct) is closed by
threading the same optional `expected_state_token` field through to the
same check. Stale writes surface as HTTP 409 with a message telling the
caller to refresh -- never a silent overwrite (Journey 5, proven directly
with two independently-signed-in reviewer sessions in
`tests/test_local_identity_multi_user.py::test_two_reviewers_stale_
write_is_rejected_not_silently_overwritten`).

`POST /api/review-queue/bulk-correct` is a known, disclosed exception --
see "Known bounded gaps" below.

No new locking or distributed consensus was built; per-item optimistic
concurrency (compare-then-write, reject on mismatch) is what the milestone
brief asked for and what the existing mechanism already provided.

## Meaningful audit trail

`AuditLogEntryModel` (`audit_log_entries`) is a genuine first-of-its-kind
table in this codebase: existing "provenance" precedents
(`camera_configuration_revisions`, `ReviewLabelModel`'s own lineage
columns, the boot-identity/replacement columns bolted onto
`camera_sources`) are each one dedicated table or bolt-on column per
feature, not a cross-cutting log. `id`, `created_at`, `actor_user_id`,
`actor_display_name` (a point-in-time snapshot, not a live join -- a later
rename never rewrites how past audit history reads), `action`,
`target_type`/`target_id` (mirroring `ReviewLabelModel`'s own
polymorphic-target pair), `metadata_json` (a small, hand-picked, bounded
blob per action -- never a raw request-body dump, so a secret can never
reach this table by accident the way it could through a generic
"log everything" writer), `correlation_id` (`request.state.request_id`,
the exact same field the existing correlation-id middleware already
produces).

`ProductRepository.record_audit_event` is called from `mockingbird.api.
main` handlers immediately after an already-successful mutation, for
every action category the milestone brief names: user created/role
changed/enabled/disabled/password reset/self password change (written
atomically inside the same new repository methods, since those are new
code with no pre-existing call sites to preserve); review confirmed/
corrected/reopened/bulk-corrected/Fast-Review-undone; camera added/
reconfigured/archived; Camera Node paired/pairing revoked/replaced; Zone
created/updated/deleted/privacy changed; storage retention policy
updated; backup restored (recorded into the *newly-active, restored*
database, not the one just replaced -- see "Backup/restore identity
semantics"); installation settings updated. Deliberately does **not** log
every page view, every GET, or routine inference activity.

`GET /api/admin/audit-log` is Administrator-only, bounded (`limit`,
capped at 500).

## User administration

`web/src/pages/UsersPage.tsx` (Administrator-only, gated by the same
`ROUTE_POLICY`/nav `minRole` mechanism as everything else): list users,
create a local user with a role, change a user's role, enable/disable,
reset a user's password (revokes their sessions), and a compact recent-
audit-activity view. Deliberately small: no email invitations, no cloud
account verification, no SCIM, no directory sync, no group/team
hierarchy. The last enabled Administrator can be neither demoted nor
disabled (`cannot_remove_last_administrator`/`cannot_disable_last_
administrator`) -- a deliberate, cheap safety addition beyond the letter
of the brief, closing the one path that would otherwise force first-run
bootstrap to reopen (a materially bigger exposure window than preventing
the self-lockout in the first place).

## Organization metadata

`InstallationSettingsModel` (`installation_settings`) is one new, tiny
singleton table -- the exact `singleton_id`-primary-key idiom already
established twice (`AppSetupStateModel`, `StorageRetentionSettingsModel`);
confirmed via direct archaeology that no existing table was a cohesive fit
before adding a new one. `installation_name`/`organization_name`/
`contact_display`, display metadata only. `GET /api/settings/installation`
is deliberately public (lets a signed-out sign-in screen show a calm
installation name); `PUT /api/admin/installation-settings` is
Administrator-only. **Not** an `Organization` tenancy hierarchy -- one
Host remains one deployment/security boundary, per "Boundary" above.

## Camera Node identity separation

Device identity and human identity were already structurally separate
before this milestone (Camera Nodes authenticate via a pairing/transport
credential system with no relationship to any user table); this milestone
adds a second, parallel identity system rather than touching that one at
all. Concretely: the `device` policy tier is the *only* place this
separation is expressed in the new authorization gate, and it is a static
path-prefix rule (`/api/camera-nodes/transport/...`) evaluated before any
human-session logic runs. Deleting/disabling/resetting a human user's
password cannot affect a Camera Node's own credential (they are stored in
entirely separate tables with no foreign-key or cascade relationship);
replacing/reprovisioning a Camera Node cannot affect any human account
for the identical reason. `tests/test_local_identity_multi_user.py`
exercises the human-identity side of this boundary directly (disabling/
resetting users, role changes); the pre-existing Camera Node test suite
(`test_camera_node_*.py`, unmodified by this milestone) continues to
cover the device side independently -- the absence of any new coupling
between the two is the proof, not a new shared test.

## Local network security guidance

No reliance on `localhost` assumptions: the session cookie has no
`Domain` attribute (defaults to the exact host that set it), so it works
identically whether reached via `127.0.0.1`, `localhost`, or a real LAN
hostname/IP. `Secure` is decided dynamically per request (see
"Authentication" above) rather than hardcoded, so it never blocks a plain-
HTTP LAN deployment while still engaging correctly behind real TLS.

For a simple home deployment: this product's existing trust boundary is
the local network itself (the same boundary Camera Node pairing, RTSP
credentials, and every other local secret already accept, unencrypted at
rest, before this milestone) -- `SameSite=Lax` plus `HttpOnly` covers
ordinary CSRF risk for a same-origin SPA without inventing a bespoke CSRF-
token scheme, and a trusted-LAN household deployment reasonably accepts
plain HTTP.

For an organization deployment wanting defense against a shared/untrusted
LAN segment: run MockingBird behind a reverse proxy (nginx, Caddy, or a
household router's own TLS-terminating proxy feature) that terminates TLS
and forwards `X-Forwarded-Proto: https` -- the cookie's dynamic `Secure`
attribute already honors that header. Building ACME/PKI issuance into the
product itself was explicitly out of scope for this milestone.

## Backup/restore identity semantics

Users, password hashes, roles, and audit history are ordinary rows in the
same SQLite database everything else lives in -- they restore with the
observatory by construction, through the exact same backup/restore
mechanism the Appliance milestone already built, with no special-casing
needed. Verified directly (`tests/test_local_identity_multi_user.py::
test_backup_restore_preserves_users_roles_and_audit_history`) through the
real `POST /api/settings/backups` + `.../restore` HTTP flow: after
restore, both users' roles are intact, `has_eligible_administrator()` is
still `True` (first-run bootstrap does **not** reopen), audit history is
intact plus a new `backup.restored` entry, installation settings
survived, and the durable password hash still authenticates a fresh
sign-in.

Ephemeral active sessions are explicitly **not** required to survive a
Host replacement/restore -- `restore_local_backup` already swaps the
process-wide repository singleton (`configure_repository`), which is a
sufficient "start fresh" boundary for in-memory session-adjacent state;
nothing was added to specially preserve or invalidate a pre-restore
session token, since neither behavior is load-bearing for any acceptance
journey. Secrets (password hashes, session-token hashes) restore exactly
according to the accepted backup/security contract -- they are ordinary
column data in the same database, never separately encrypted or excluded.

## Privacy

No telemetry, no cloud account synchronization -- user identity data
never leaves the local Host. Support bundles already redact anything
matching `"password"`/`"token"`/`"secret"`/`"credential"`/`"bearer"`/
`"api_key"` in free-form log text (`mockingbird.diagnostics.support_
bundle._CREDENTIAL_SHAPED_SUBSTRINGS`, confirmed pre-existing and
unmodified) -- session cookie names/values and the `password_hash` column
name both already fall under that denylist. `support_bundle.py`'s
structured exports remain explicit allowlists of specific columns (the
existing `SupportBundleSourceSummary` pattern); this milestone added no
new structured export of user/session/audit data to the bundle, so there
is no new allowlist to audit for a leaked secret.

## Frontend session/product experience

`web/src/App.tsx` gates the entire app (not just the dashboard route, the
way the pre-existing onboarding gate did) on two sequential checks: is
setup complete (else render `OnboardingWizard`), then is there a signed-in
session (else render `SignInPage`) -- fail-closed while unknown (`authStatus:
"loading"` renders nothing), never fail-open the way the older, lower-
stakes onboarding check does. A single central `onSessionExpired` hook in
`web/src/api/client.ts` fires on any 401 from any API call, so a session
that expires or gets revoked mid-use drops back to the sign-in screen
automatically rather than surfacing a confusing generic error. Nav items
are filtered by role (`minRole`) for a calm, uncluttered UI, never as the
actual authorization boundary. The account menu (display name, role,
sign-out) is the only place role labels appear outside admin/audit
surfaces and review provenance, per "do not plaster role labels across
every screen."

## Migration discipline

Schema 49 -> 50, one migration function
(`_migrate_to_local_identity_multi_user_access`), additive only: four new
tables (`users`, `user_sessions`, `audit_log_entries`,
`installation_settings`) and one new nullable column
(`review_labels.reviewed_by_user_id`). Nothing is backfilled: an upgraded
installation starts with zero `users` rows (exactly the "no users exist"
state first-run bootstrap already expects) and every pre-existing
`review_labels` row simply gets `reviewed_by_user_id = NULL` -- an honest
"no signed-in actor," never a fabricated one, mirroring this same table's
existing `review_origin`/`reviewer_identity` "legacy_unattributed"/`NULL`
discipline from the schema-32 migration. Tested directly
(`test_legacy_review_row_with_no_actor_stays_honestly_unattributed`):
constructing a `ReviewLabelModel` row exactly the way a pre-migration row
would look (`reviewed_by_user_id=None`) round-trips through the API
unchanged.

## Testing

`~103` pre-existing test files call protected endpoints over real HTTP
with no session at all -- retrofitting every one of them to authenticate
was judged out of proportion to this milestone's scope. `mockingbird.api.
auth` bypasses authorization by default whenever `"pytest" in sys.modules`
(the exact convention already established by `mockingbird.storage.
database._running_under_pytest` and `mockingbird.api.main._patch_
testclient_for_pytest` for this identical class of problem) -- this can
never be true for the packaged Windows runtime or an ordinary launch
(pytest is a `[project.optional-dependencies] test` extra no runtime
import path pulls in). A handler that needs `acting_user` under the
bypass (review attribution, audit logging) falls back to a synthetic
`_TEST_DEFAULT_USER`, lazily backed by a *real* `users` row the first time
it is actually needed (found necessary by direct execution: a purely
in-memory synthetic identity made `PRAGMA foreign_key_check` -- already
asserted clean by an existing test -- correctly flag a dangling
reference) and deliberately given `role="viewer"` (found necessary by
direct execution: `role="administrator"` made every bypassed test's
database look like first-run bootstrap had already happened, breaking
`test_first_run_onboarding.py`'s own assumption).

`tests/test_local_identity_multi_user.py` is the one place the bypass is
turned back off (`_TEST_ENFORCE_AUTH_HEADER` on every request) to actually
exercise real enforcement -- password hashing; bootstrap race-safety/
replay-proofing/no-default-credentials; session lifecycle (disable/enable
and role changes taking effect immediately, self-password-change session
preservation, admin-reset revocation); Viewer/Reviewer/Administrator
authorization over real HTTP; review attribution (including the negative
case: non-human origin and an explicit `reviewer_identity` are never
overridden); the two-reviewers stale-write conflict (Journey 5); the audit
trail (content and no-secrets); the legacy-row case (Journey 11); and
backup/restore identity semantics (Journey 10).

`web/e2e/onboarding.spec.ts` (its own genuinely fresh instance) proves
Journey 1 end-to-end in a real browser: welcome -> create administrator
account -> (now signed in) -> storage -> camera -> finish -> Dashboard,
reload-resumes-correctly at each step, bootstrap does not reappear after
sign-out/sign-in. The shared `playwright.config.ts` suite's ~18
pre-existing spec files predate authentication; rather than touch every
one, `web/e2e/global-setup.ts` bootstraps a real Administrator once before
the whole suite and every spec starts already signed in via a shared
`storageState` -- Playwright's own documented pattern for this exact
problem, requiring no change to any existing spec file (verified directly:
`dashboard-live-camera-ownership.spec.ts` passes unmodified).

## Explicit exclusions

Not built, per the governing milestone brief: LDAP, Active Directory,
Entra ID, generic OIDC, SAML, SCIM, SaaS tenancy, billing, subscriptions,
Multi-Site, organizations containing multiple deployments, email
invitations, cloud user accounts, mobile/PWA, notifications, HA
clustering, Kubernetes, remote relay, public-Internet-exposure
automation, ACME/PKI infrastructure, and fine-grained enterprise RBAC.

## Known bounded gaps

- `POST /api/review-queue/bulk-correct` has no per-item optimistic-
  concurrency check (its schema has no per-item `expected_state_token` --
  one label is applied to N target_ids in one request; adding a
  heterogeneous per-item token list would be a larger, separate schema
  redesign not clearly justified by the acceptance journeys, which center
  on a single-Visit scenario). The primary interactive single-Visit review
  flow (`/api/review-labels`, `/revision`, `/reopen`, Fast Review) is
  fully protected.
- Frontend button-level hiding for admin/reviewer-only actions was applied
  at the nav-item level (top-level pages), not exhaustively audited
  button-by-button inside every existing page component -- the server-
  side gate is what actually enforces the boundary either way (proven
  directly over real HTTP for every role), so a visible-but-rejected
  button in some deep page corner is a UX rough edge, not a security gap.
- `reviewer_identity` remains technically client-suppliable via the raw
  API even when authenticated (never force-overridden -- see "Review
  attribution" above for why); `reviewed_by_user_id` is the trustworthy
  field for anything that needs to actually rely on who acted.
- Camera/RTSP/ONVIF credentials remain stored plaintext at rest, exactly
  as before this milestone -- unchanged and out of scope; user password
  hashes are the first genuinely hashed secret in this schema.
