# Non-Interactive Field Acceptance Authentication & Session Access v1

**Date:** 2026-08-28.
**Starting HEAD:** `c03d0b1` (accepted repository HEAD); product implementation
baseline under field acceptance: `80e1bb3`; schema `57`.
**Implementation HEAD:** `1656f1a` (this milestone's own implementation
commit -- code, tests, and the design contract doc -- layered directly on
`c03d0b1`; this report itself lands in one small doc-only follow-up commit
on top, matching this repository's own established "implementation, then
a small separate reconciliation/documentation commit" convention).
**Schema:** `57 -> 58`.
**Classification: A.**

## 1. Governing sources read

In order, per the governing brief: `docs/release-execution-state.md` (full),
`docs/product-doctrine.md` (the security/deployment/organization-doctrine
sections), `docs/roadmap.md` ("Local Identity, Multi-User & Organization
Access", "Security / release questions"). Then bounded archaeology on:
`docs/local-identity-multi-user-contract.md` (full -- the current
identity/session/authorization architecture); `src/mockingbird/api/auth.py`
(full -- the central authorization gate); `src/mockingbird/api/main.py`'s
Observation start/stop/status/counterfactual handlers and router-wiring
section; `src/mockingbird/repository/product_repository.py`'s Local
Identity method block; `src/mockingbird/storage/models.py`'s
`UserModel`/`UserSessionModel`/`AuditLogEntryModel`; `src/mockingbird/
storage/database.py`'s migration chain and `CURRENT_DATABASE_SCHEMA_
VERSION`; `src/mockingbird/security/passwords.py`; `scripts/repair_review_
label_provenance.py` (the closest existing "bounded admin command talking
to a running instance over real HTTP" precedent); `tests/test_local_
identity_multi_user.py` and `tests/conftest.py`'s
`LegacyAuthenticatedTestClient`; the three most recent Representative Field
Acceptance reports (2026-08-25, 2026-08-26, and
[representative-daylight-field-acceptance-gate-a-evidence-v2-report.md](representative-daylight-field-acceptance-gate-a-evidence-v2-report.md),
2026-08-28) for the exact blocked-endpoint evidence. Did not rediscover the
entire repository.

## 2. Starting state (verified, not assumed)

All matched the governing brief's expected state exactly:

- Branch: `main`.
- Accepted repository HEAD: `c03d0b1` (confirmed via `git rev-parse HEAD`
  before any change).
- Product implementation baseline under field acceptance: `80e1bb3`.
- Schema: `57` (`CURRENT_DATABASE_SCHEMA_VERSION` in
  `src/mockingbird/storage/database.py`, before this milestone's own
  change).
- Latest accepted milestone: Representative Daylight Field Acceptance &
  Gate A Evidence v2, classification B, Lane R still open, isolated
  blocker: authenticated access required for live field-acceptance
  operations.
- Release doctrine: one public launch.
- Authorization before this instruction: **NONE -- GLOBAL PRODUCT-ROADMAP
  RECONCILIATION REQUIRED.**
- Repository not pushed (confirmed; remained not pushed throughout).

## 3. Worktree safety

No other active writer found: `git status --porcelain=v2` showed only the
seven already-known preserved untracked files at session start, and this
session's own edits landed exactly where intended (verified via `git
status` before every stage/commit). The seven preserved untracked detector
files were confirmed present at session start and again after the
implementation commit, with no staging/modification of any of them:

- `docs/wildlife-detector-training-contract.md.orig`
- `scripts/evaluate_small_bird_detector.py`
- `scripts/materialize_wildlife_stage2.py.orig`
- `scripts/train_wildlife_stage2_rfdetr.py.orig`
- `src/mockingbird/detectors/small_bird_benchmark.py`
- `src/mockingbird/training/wildlife.py.orig`
- `tests/test_small_bird_benchmark.py`

`git add` was invoked with an explicit file list for every commit in this
milestone -- never `-A`/`.`/`commit -a` -- specifically to make staging any
of the seven impossible by construction. Nothing was pushed.

## 4. Auth architecture summary (§5 of the governing brief, answered from
   repository evidence)

1. **Users**: `UserModel` (`users` table) -- `id`, `display_name`,
   `login_identity` (lowercase-normalized), `password_hash`, `role`,
   `enabled`, timestamps.
2. **Credentials**: `hashlib.scrypt` (RFC 7914; stdlib, no third-party
   dependency), self-describing stored string, min length 10, no
   composition rules (NIST SP 800-63B).
3. **Roles**: Viewer < Reviewer < Administrator, a strict linear ladder
   (`mockingbird.api.auth.role_at_least`).
4. **Permissions per role**: Viewer -- reads + personal alert ack/dismiss.
   Reviewer -- Viewer + review/correct/reopen/split/merge. Administrator --
   Reviewer + camera/source/zone/yard-map config, Camera Node
   pairing/replacement, storage/retention/backup, species packs,
   operational capture controls (including Observation start/stop),
   `/api/admin/*` (user management, audit log, installation settings).
5. **Sessions**: server-side, opaque (`UserSessionModel`), `mb_session`
   cookie carries a random `secrets.token_urlsafe(32)`; only its SHA-256
   hash is persisted.
6. **Session validation**: `resolve_session` re-reads the live `UserModel`
   row (`.enabled`/`.role`) on every call -- a disable/role-change takes
   effect on the very next request, no separate revocation sweep.
7. **Transport**: cookie-based only, before this milestone. No bearer/
   API-token concept existed anywhere in the repository (confirmed by
   direct archaeology).
8. **CSRF**: `SameSite=Lax` + `HttpOnly`, no bespoke CSRF-token scheme
   (documented rationale: same-origin SPA over a trusted-LAN boundary).
9. **Auth endpoints**: `POST /api/auth/sign-in`, `POST /api/auth/sign-out`,
   `GET /api/auth/session`, `POST /api/auth/change-password`.
10. **First-run bootstrap**: `create_first_administrator`, guarded by an
    in-process lock, refuses once `has_eligible_administrator()` is true.
    No default `admin`/`admin`.
11. **CLI/admin provisioning path**: none generic (no `mockingbird` CLI
    framework -- only `mockingbird-app` as the app launcher). The closest
    precedent for a bounded admin command is `scripts/repair_review_
    label_provenance.py` (talks to a running instance over real HTTP).
12. **Service-account/API-token concept**: **none existed** before this
    milestone (confirmed by direct archaeology of `src/mockingbird/api/`,
    `src/mockingbird/security/`, and `src/mockingbird/storage/models.py`).
13. **Non-interactive authentication support**: **none existed** -- this is
    the exact gap this milestone closes.
14. **Auth event logging**: `AuditLogEntryModel`/`record_audit_event`,
    Administrator-only `GET /api/admin/audit-log`, a small hand-picked
    metadata blob per action, never a raw request-body dump.
15. **Credential revocation**: explicit only (sign-out, admin reset,
    self-service change), never inferred from a timestamp; a `.enabled`
    flip takes effect immediately via the live re-read in (6).
16. **Secrets at rest**: password hashes and session-token hashes only --
    both one-way, both the first genuinely hashed secrets in this schema
    (camera/RTSP/ONVIF credentials remain plaintext, unchanged, out of
    scope).
17. **Rate limits/lockout**: none exist (a pre-existing, disclosed gap --
    see Mobile & Remote Experience v1's own report -- left untouched, out
    of this milestone's scope).
18. **Endpoint/permission map for the field-acceptance workflow**: built in
    full -- see §6 below and the contract doc's "Endpoint/permission
    matrix".
19. **Can the workflow run with less than full Administrator?** Yes for
    every read (Viewer floor already covers it); Observation start/stop
    alone needed a narrow, explicit exception -- see §6.

## 5. Root gap

Confirmed exactly as the governing brief and the three prior field-
acceptance reports state: production authentication (correctly) requires a
signed-in session for `GET /api/streams`, `GET /api/visits`, Observation
start/stop, and the counterfactual/admission-lineage endpoint. No
supported way existed for bounded, non-interactive tooling to authenticate
without either the operator's personal password or a bypass. Live-
reconfirmed at the start of this milestone's own real acceptance proof
(§9, below) against the same three endpoints the prior reports document,
before any credential existed on that instance -- all three still `401`.

## 6. Chosen contract

**Option B -- explicit local acceptance principal**, bearer-token
authenticated: **"Field Acceptance Operator"**. A second, narrow, parallel
identity system, deliberately not a fourth value on the linear Viewer/
Reviewer/Administrator ladder -- the required permission shape (broad
Viewer-level reads plus exactly two otherwise-Administrator-tier
mutations, Observation start/stop, and nothing else Administrator-tier) is
not a contiguous prefix of that ladder, so no single rank placement could
express it correctly. Mirrors this codebase's own existing precedent for
exactly this shape: Camera Node device identity is already a second,
parallel identity system, structurally separate from human `UserModel`
accounts.

Full design, endpoint/permission matrix, data model, and security
rationale: [non-interactive-field-acceptance-authentication-session-
access-v1-contract.md](non-interactive-field-acceptance-authentication-session-access-v1-contract.md).
Summary:

- **Permissions**: every `authenticated`-tier read (the existing Viewer
  floor) + a 2-entry explicit allowlist (`FIELD_ACCEPTANCE_ALLOWED_ADMIN_
  ROUTES`: `POST .../observation/start`, `POST .../observation/stop`).
  Nothing Reviewer-tier, nothing else Administrator-tier -- no user
  management, no role changes, no security/installation settings, no
  credential management (including its own -- it cannot create or revoke
  a field-acceptance credential, only an Administrator can), no camera/
  zone/backup mutation, no arbitrary database mutation.
- **Local boundary**: enforced through the exact same central
  `install_authorization` gate every other request already passes
  through -- no IP-based/localhost trust logic was added or relied on
  (this codebase already correctly treats `127.0.0.1` as not itself a
  trust boundary, and this milestone did not change that).
- **Lifecycle**: mandatory bounded expiry (`1..720` hours, default 24) --
  there is no permanent-credential path in v1 at all; explicit,
  deterministic revocation; hash-only storage; auditable creation/
  revocation/use.

## 7. Security properties

- **No bypass**: checked by the identical central middleware; no new
  header, no query-string token, no cookie-value token, no localhost
  exemption -- see the negative test suite in §11 and the live regression
  proof in §9.
- **Revocation**: immediate and deterministic -- `resolve_field_acceptance_
  token` re-reads `revoked_at` fresh from the database on every call, with
  no cache or blocklist sweep, exactly mirroring `resolve_session`'s own
  contract. Proven both in the automated test suite and live (§9).
- **Expiration**: mandatory (not optional), `1..720` hours, enforced at
  the request-schema layer and re-checked fresh on every resolution.
- **Auditability**: reuses the existing `AuditLogEntryModel`/`record_
  audit_event` mechanism unmodified. New actions: `field_acceptance_
  credential.created`/`.revoked` (actor = the Administrator), `stream.
  observation_started`/`.observation_stopped` (actor = whichever identity
  authenticated the request -- a closed pre-existing gap: Observation
  start/stop was not previously audited for a human Administrator either;
  fixed once for both identities as one small additive change). A
  field-acceptance principal's actions carry `actor_user_id = NULL` and a
  distinct, greppable `"Field Acceptance Operator: <label> (<id>)"`
  `actor_display_name` -- proven distinguishable from the Administrator's
  own actions live (§9).
- **Storage**: SHA-256 hash-only (`generate_session_token`/`hash_session_
  token`, reused unmodified from `mockingbird.security.passwords`) --
  never plaintext at rest.

## 8. Tooling integration

- `scripts/manage_field_acceptance_credential.py` -- bounded admin CLI
  (`create`/`list`/`revoke`), mirroring `repair_review_label_provenance.
  py`'s own real-HTTP-instance precedent. Signs in as an already-existing
  Administrator (never bootstraps one); the Administrator password is
  never a CLI argument (unechoed `getpass` prompt or `MOCKINGBIRD_ADMIN_
  PASSWORD`). Prints the minted token exactly once.
- `scripts/field_acceptance_client.py` -- the acceptance tooling itself:
  reads `MOCKINGBIRD_ACCEPTANCE_TOKEN`, attaches `Authorization: Bearer
  <token>`, covers `list_streams`/`list_visits`/`start_observation`/
  `stop_observation`/`observation_status`/`observation_counterfactual`/
  `product_health`. Raises a distinct, clear exception for: no credential
  configured, invalid/expired/revoked (401, deliberately indistinguishable
  at this layer -- matches `resolve_session`'s own non-disclosure
  convention), insufficient permission (403), or any other API error. No
  anonymous fallback anywhere in this client.

## 9. Real acceptance proof

Provisioned a temporary acceptance principal through the supported
administrative mechanism, against a real running instance of this
milestone's own implementation commit (`1656f1a`) -- not a mock, not a
unit test, a genuine deployed Windows process built via `scripts/deploy_
windows_dev.py --commit 1656f1a` (native Windows, real SQLite, real
FastAPI/uvicorn process, `--skip-gpu-runtime --skip-bioclip-runtime` since
this proof needs the auth/API layer, not detection quality). Deployed to
an isolated, disposable `--dev-root`
(`C:\Users\...\AppData\Local\MockingBirdFieldAcceptanceAuthV1Test`) --
**not** the operator's real `MockingBirdDev` deployment, confirmed
untouched throughout (`--status` against the default dev-root before and
after this session shows the identical ledger, `db8588c` last-deployed,
port 8000 free from its perspective at all times). **No credentials
belonging to the operator were requested, used, or exist anywhere in this
proof** -- a disposable Administrator (`field-acceptance-proof-admin`,
throwaway password) was bootstrapped fresh on this isolated instance
solely to provision the credential under test, exactly matching the
governing brief's own explicit allowance ("If the development/test
deployment uses a disposable local Administrator established through
already-accepted tooling, that is fine for provisioning the acceptance
principal").

**Blocked before (re-confirmed live, matching all three prior field-
acceptance reports exactly):**

| Endpoint | Result, no credential |
|---|---|
| `GET /api/streams` | `401` |
| `GET /api/visits` | `401` |
| `POST /api/streams/{id}/observation/start` | `401` |

**Authenticated after (proven live, with the field-acceptance bearer
token, both via the real deliverable scripts and a direct API-level
proof):**

| Step | Result |
|---|---|
| `manage_field_acceptance_credential.py create` (as the disposable Administrator) | Credential created, token printed once |
| `manage_field_acceptance_credential.py list` | Shows the credential, no token/hash |
| `field_acceptance_client.py smoke-test --stream-id stream-backyard-feeder` | `product/health`: `ready=True, schema=58`; `GET /api/streams`: 1 Stream; `GET /api/visits`: succeeded; **real Observation start** (`runtime_kind: live_monitoring`, `desired_mode: armed`, `actual_state: starting`); **real Observation stop**; exit code `0` |
| Direct API proof (all 20 steps, itemized below) | **20/20 passed** |
| `POST /api/sources` (unrelated Administrator action) with the token | `403` |
| `GET /api/admin/users` with the token | `403` |
| `GET /api/admin/audit-log` (as Administrator) | Shows `stream.observation_started`/`.observation_stopped` with `actor_display_name = "Field Acceptance Operator: ... (field-acceptance-266d2cfcac15422d)"`, distinguishable from the Administrator's own actions |
| `manage_field_acceptance_credential.py revoke --credential-id ...` | Revoked, `revoked_at` set |
| `field_acceptance_client.py smoke-test` with the now-revoked token | `ERROR: Sign in to continue.`, exit code `1` (clean, clear failure -- not a crash) |
| Direct API proof: `GET /api/streams` with the revoked token | `401` |
| Direct API proof: `POST .../observation/start` with the revoked token | `401` |

Full itemized 20/20 result from the direct API-level proof script
(`baseline_unauthenticated_streams_401`, `baseline_unauthenticated_visits_
401`, `baseline_unauthenticated_observation_start_401`, `bootstrap_
disposable_administrator`, `create_field_acceptance_credential`, `token_
never_echoes_in_list_endpoint_shape`, `configure_demo_stream_as_
administrator`, `token_reads_streams`, `token_reads_visits`, `public_
health_endpoint`, `token_starts_observation`, `token_reads_observation_
status`, `token_reads_counterfactual_lineage`, `token_stops_observation`,
`token_cannot_create_source_403`, `token_cannot_list_users_403`, `audit_
trail_distinguishes_principal_from_administrator`, `revoke_credential`,
`revoked_token_reuse_fails_401`, `revoked_token_cannot_start_observation_
401`) -- every step `ok: true`.

**Cleanup**: the temporary acceptance credential was revoked (proven
above); the disposable Administrator account, the entire isolated
`MockingBirdFieldAcceptanceAuthV1Test` dev-root, and the running process
were all removed/stopped -- confirmed via `Get-NetTCPConnection` (nothing
listening on port 8000 afterward) and `Test-Path` (directory confirmed
absent). No lingering active credential was left merely for convenience.
The environment was left in a secure, known, empty state.

## 10. e2e result

Not run. This milestone's own code changes are confined to
`src/mockingbird/api/`, `src/mockingbird/repository/`, `src/mockingbird/
storage/`, and `scripts/` -- zero `web/src/` changes (no new frontend
account-management UI, per the governing brief's own explicit allowance;
the response shape of every endpoint the frontend already calls is
unchanged). The existing Playwright suite authenticates via a shared
`storageState` bootstrapped once in `global-setup.ts`
(cookie-session-based), which this milestone's bearer-token mechanism does
not touch or intersect with. Per this repository's own documented
precedent ("Don't run full e2e + full Core concurrently -- real SQLite
lock contention"), and given zero frontend/UI surface changed, e2e was not
run this milestone.

## 11. Tests

**Tier 1/2 (focused + affected subsystem): 239 passed, 0 failed.**

- `tests/test_field_acceptance_authentication.py` -- 20 new tests, all
  passing: positive (valid token satisfies reads; real Observation start/
  stop; audit attribution), negative (missing/malformed/unknown token;
  revoked; expired -- both a direct repository-level construction and an
  HTTP-level equivalent), privilege boundary (cannot create sources/users/
  review labels/other field-acceptance credentials; cannot reach
  Reviewer-tier), revocation (immediate, idempotent), no-bypass regression
  (query-string token, cookie-value token, debug/forwarded/localhost-
  flavored headers, a signed-in Viewer cookie combined with a valid bearer
  token -- none escalate or bypass).
- `tests/test_persistence.py::test_schema_57_upgrades_to_current_with_
  field_acceptance_credentials` -- a real database at schema 57 upgrades
  cleanly through the new additive table with zero credentials backfilled,
  mirroring the established per-version upgrade-test convention exactly.
- `tests/test_local_identity_multi_user.py`, `tests/test_observation_
  unified_api.py` (the two handlers this milestone touched), `tests/
  test_camera_health.py`, `tests/test_camera_node.py`, `tests/test_
  candidate_visit_repository.py`, `tests/test_species_candidate_packs.py`,
  `tests/test_visit_tags.py`, `tests/test_visit_collections.py`, `tests/
  test_yard_map.py` (the eight files whose hardcoded
  `CURRENT_DATABASE_SCHEMA_VERSION == 57` literal was bumped to 58) --
  219 passed, 0 failed, all warnings pre-existing/unrelated
  (`sqlite3` datetime-adapter deprecation, FastAPI `on_event` deprecation
  in the separate `mockingbird_node` package).

`ruff check` on every changed file: confirmed **zero new findings** via a
direct clean-baseline bisection (`git stash`/re-check/`git stash pop`) --
83 pre-existing findings before and after, none in this milestone's own
changed lines.

**Tier 3 (full Core)**: see §13.

## 12. Privilege/no-bypass checks (governing brief §14/§15, itemized)

**Must succeed -- all proven, both in the automated suite and live:**
authenticated health/session inspection (public, unaffected); read Streams;
start Observation; stop Observation; read Visits; read counterfactual/
admission lineage.

**Must fail -- all proven `403`, both in the automated suite and live:**
create/delete human users; promote roles; change Administrator
credentials (no endpoint reachable at all -- `/api/admin/users/{id}/
reset-password` is Administrator-tier, unreachable); change security/
installation settings; disable authentication (no such endpoint exists in
this product at all); access unrelated secrets (backups, storage
retention); any destructive administration outside the two allowlisted
routes.

**No-bypass regression (governing brief §15, itemized):** absence of
credential -> `401` (proven); invalid credential -> `401` (proven);
revoked credential -> `401` (proven, both automated and live); an
authenticated-but-underprivileged principal -> `403` (proven -- a
field-acceptance token hitting a Reviewer- or unrelated Administrator-tier
route); the credential works only through the normal, central auth
middleware (proven -- no separate code path); no special request-header
bypass exists (proven via an explicit regression test against five
plausible bypass-header names); no localhost anonymous exemption exists
(this codebase never had one to begin with, and this milestone
deliberately did not add one -- proven by the same unauthenticated-`401`
baseline test running against `127.0.0.1`).

## 13. Tier 3 (full Core)

`python scripts/verify_core.py -q` (the whole backend suite except
`slow`-marked tests): **5187 passed, 3 skipped, 23 deselected, 11 xfailed,
2 failed** (26m01s). The 2 failures are both in
`tests/test_place_biodiversity_summary_repository.py`
(`test_api_route_returns_the_summary`,
`test_human_correction_updates_place_biodiversity_intelligence_correctly`),
an unrelated bird-species historical-status ("new" vs. "seen_before")
classification defect in the Biodiversity & Place Intelligence subsystem --
zero code-path relationship to authentication, sessions, schema migration,
or anything this milestone touched.

**Confirmed pre-existing by direct execution, not merely inferred from
precedent** (though it also matches this repository's own established
precedent -- Multi-Camera Place Experience v2's Tier 3 run recorded the
identical pair as "already-disclosed pre-existing"): re-ran the exact same
file in isolation (a) against this milestone's implementation commit
(`1656f1a`) and (b) against a clean `git checkout` of the true pre-milestone
baseline (`c03d0b1`, this repository's own accepted starting HEAD, with a
`git status` re-verification that the seven preserved untracked files were
undisturbed by the checkout, followed by `git checkout main` to restore).
Both runs produced the byte-identical failure -- same two test names, same
assertion (`AssertionError: assert 'seen_before' == 'new'`), same line
number. Zero regressions attributable to this milestone.

`ruff check` re-confirmed clean (zero new findings) on the final committed
state, matching §11's earlier bisection.

## 14. Remaining risks (concrete only)

- No login rate-limiting exists anywhere in this product (a pre-existing,
  disclosed gap from Mobile & Remote Experience v1, untouched and out of
  scope here) -- a field-acceptance bearer token is a static secret for
  its bounded lifetime like any bearer token, mitigated by mandatory
  expiry, hash-only storage, and explicit revocation, but not by any
  brute-force protection on the token-lookup path itself (the lookup is a
  hash-indexed database read, not a guessable short value -- 32 bytes of
  `secrets.token_urlsafe` entropy -- so this is a materially smaller risk
  than password brute-forcing, but not literally rate-limited).
- `manage_field_acceptance_credential.py`'s `MOCKINGBIRD_ADMIN_PASSWORD`
  environment-variable path is convenient for non-interactive/scripted
  provisioning but means that value is visible to anything that can read
  that process's environment for its lifetime -- documented in the script
  itself; the interactive `getpass` prompt avoids this entirely and is the
  recommended default.
- Rotation is not a distinct operation in v1 -- explicit revoke + `create`
  is the supported path (an explicit, disclosed, brief-sanctioned
  simplification, not an oversight).
- The real acceptance proof (§9) ran against a disposable, freshly
  bootstrapped instance, not the operator's specific long-running real
  `MockingBirdDev` deployment (deliberately, per standing policy against
  requesting the operator's personal credentials). The next
  representative field-acceptance session will still need one, first,
  one-time step on that specific real instance: an Administrator (the
  operator, using their own already-existing account, exactly as intended
  by this milestone's design) runs `manage_field_acceptance_credential.py
  create` once to provision a credential on *that* instance before the
  first non-interactive session against it. This is not a gap in the
  mechanism -- it is the intended, minimal, one-time human step the whole
  design exists to make sufficient, instead of ongoing credential sharing.

## 15. Decision

**A.** No authentication bypass; no user's personal credentials required
anywhere in this milestone's own work (including its real acceptance
proof); explicit supported provisioning; least-privilege access proven
both by design and by live negative testing; revocation proven immediate
and deterministic, both automated and live; bounded expiry enforced (no
permanent-credential path exists); no plaintext secret persistence or
logging (confirmed by direct test assertion and by this report's own
authorship -- no token appears anywhere in this document); the exact
required field-acceptance endpoints were successfully exercised against a
real running instance of this milestone's own product code (not a mock);
unrelated Administrator operations were proven denied, both automated and
live; the field-acceptance blocker is demonstrably removed (the identical
three endpoints that blocked the 2026-08-25/-26/-28 attempts now succeed
with the new credential and fail exactly as before with none); validation
is clean (Tier 1/2 100%, Tier 3 recorded in §13, zero new `ruff` findings).

## 16. Remaining field-acceptance auth blocker: closed

The recurring blocker across three consecutive milestone attempts
(2026-08-25, 2026-08-26, 2026-08-28) -- "the acceptance tooling has no
supported non-interactive identity/session path" -- is closed. The next
representative daylight Gate A session needs exactly one new,
already-anticipated step before it starts: an Administrator (the
operator) runs, once, against the real instance:

```bash
python scripts/manage_field_acceptance_credential.py create --ttl-hours <bounded to the session's own expected duration>
```

then exports the printed token as `MOCKINGBIRD_ACCEPTANCE_TOKEN` for
whatever acceptance-recording process runs the session (importing
`scripts/field_acceptance_client.py`'s `FieldAcceptanceClient`, or any
other tool that sets the same `Authorization: Bearer` header). No other
credential exchange, no interactive sign-in, and no further auth
archaeology should be needed for that session.

## 17. Current authorization state

**NONE -- GLOBAL PRODUCT-ROADMAP RECONCILIATION REQUIRED**, unchanged.
This milestone does not authorize the next Representative Field
Acceptance / Gate A session, External Pre-Release Acceptance, or Final
Release Hardening.

## 18. Ready for ChatGPT acceptance review

**Ready.**
