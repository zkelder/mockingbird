# Login Rate-Limiting & Authentication Abuse Resistance v1 -- report

A RELEASE-SECURITY milestone. Adds bounded, local-first brute-force/abuse
resistance to human login (`POST /api/auth/sign-in`), the one authentication
surface in this product that had generic, enumeration-safe failure behavior
but no attempt counting, no delay, and no throttling at all -- a real,
previously-disclosed, pre-existing gap (first found by Mobile & Remote
Experience v1's own security review; re-disclosed by several milestones
since, most recently Non-Interactive Field Acceptance Authentication &
Session Access v1). Pairing already has its own rate limiting
(`mockingbird_node.app`'s `_MAX_PAIR_ATTEMPTS`); human login did not.

## Starting state

- Branch `main`, accepted HEAD `a846655` -- confirmed to match exactly
  before any change (matches the governing brief's own expected starting
  state).
- Schema `v58` -- confirmed unchanged; this milestone adds zero tables,
  zero columns, zero migrations.
- Latest accepted milestone: Historical Species-Status ("New" vs. "Seen
  Before") Correctness v1.
- The seven preserved untracked files (`docs/wildlife-detector-training-
  contract.md.orig`, `scripts/evaluate_small_bird_detector.py`, `scripts/
  materialize_wildlife_stage2.py.orig`, `scripts/train_wildlife_stage2_
  rfdetr.py.orig`, `src/mockingbird/detectors/small_bird_benchmark.py`,
  `src/mockingbird/training/wildlife.py.orig`, `tests/test_small_bird_
  benchmark.py`) were checksum-verified byte-identical at the start of this
  session and again at its close -- untouched throughout, including across
  a deliberate `git stash push -u`/`pop` round-trip used for a ruff
  clean-baseline bisection (see "Tests," below). An untracked root
  `uv.lock` reappeared mid-session -- the same ordinary, never-gitignored
  `uv run`/`uv sync` side effect this file's own recurring history already
  documents; not a milestone artifact, and not one of the seven preserved
  files.
- No active worktree writer: confirmed via `git log`'s own unmoved history
  at session start.
- Current authorization before this instruction: NONE -- GLOBAL
  PRODUCT-ROADMAP RECONCILIATION REQUIRED; this milestone was directly
  authorized outside `docs/release-execution-state.md`, as that file's own
  established convention already permits for a named, scoped
  release-security milestone.

**Pre-fix auth behavior (root-caused before any fix, per the governing
brief's own ten diagnostic questions):**

1. **Endpoint:** `POST /api/auth/sign-in` (`mockingbird.api.auth.build_auth_
   router`'s `sign_in` handler) is the only credential-accepting endpoint.
2. **Verifying method:** `ProductRepository.authenticate_user` -- looks up
   `UserModel` by normalized `login_identity`, checks `.enabled`, then
   `mockingbird.security.passwords.verify_password` (`hashlib.scrypt`,
   `N=2**15, r=8, p=1`, constant-time digest compare).
3. **Enumeration-safe already:** yes, deliberately -- unknown user, wrong
   password, and disabled user all returned the identical `None`, mapped
   by the endpoint to one generic `401 {"detail": "Incorrect login
   identity or password."}`. Confirmed structurally correct and left
   unchanged in shape by this milestone.
4. **Sessions created:** `ProductRepository._create_session_in_session`,
   called only from inside `authenticate_user`'s own success branch (and
   from `create_first_administrator`'s bootstrap) -- confirmed the only
   two session-minting call sites in the codebase.
5. **Synchronous:** yes -- `authenticate_user` is a plain synchronous
   method; the `async def sign_in` endpoint calls it directly on the event
   loop (pre-existing, unchanged by this milestone; not itself a rate-
   limiting concern, since the limiter's own state access is a cheap,
   non-blocking in-memory operation, not a new blocking cost).
6. **Client identity available:** `login_identity` (from the request
   body); `request.client.host` (the real direct TCP peer address, Starlette-
   populated from the ASGI server, confirmed **never previously read
   anywhere in `mockingbird.api.auth` or `.main`**); no separate session/
   client identifier exists pre-authentication; no localhost distinction is
   made anywhere in the authorization stack (confirmed by direct
   archaeology -- `mockingbird.api.auth` has no `127.0.0.1`/`localhost`
   special case of any kind).
7. **Reverse-proxy/Tailscale reliability:** this deployment establishes
   **no trusted-proxy boundary** for `X-Forwarded-For`/similar headers
   anywhere -- the one existing forwarded-header use
   (`_request_is_secure`'s `X-Forwarded-Proto` check) is explicitly
   documented in its own docstring as "trusted here only to decide a
   cookie attribute, never for any authorization decision." Tailscale
   traffic reaches the Host directly (no NAT rewrite at that layer); an
   optional self-hosted reverse proxy would make every request appear to
   originate from the proxy's own address. Both are accounted for in the
   design (see "Design decision," below).
8. **Failed attempts audited:** no -- confirmed zero audit-log writes
   anywhere on the pre-fix failure path.
9. **Successful login audited:** no -- confirmed zero audit-log writes on
   the pre-fix success path either (only user-management actions --
   created/role-changed/enabled/disabled/password-reset/self-password-
   change -- were audited before this milestone).
10. **Existing DB/schema structures:** `AuditLogEntryModel`/`audit_log_
    entries` (append-only, Administrator-readable via `GET /api/admin/
    audit-log`, already the established mechanism for exactly this class
    of security-relevant identity event) was reused as-is, with zero schema
    change, for the new bounded audit events this milestone adds. No new
    table was created or needed for the throttle *state* itself -- see
    "Design decision."

## Threat model

Covered explicitly, matching the governing brief's own required categories:

- **Online password guessing** (repeated bad passwords, one account):
  bounded by the account-keyed dimension -- 3 free attempts, then a
  1s/2s/5s/15s/30s/60s ladder, combined with the pre-existing real
  per-guess `hashlib.scrypt` cost.
- **Username spray** (many usernames, one client/source): bounded by the
  source-keyed dimension -- a shared per-source counter accumulates across
  every distinct username tried from that source, regardless of whether
  any of them are real.
- **Distributed/local-network spray** (many sources, one account): bounded
  by the account-keyed dimension, which is source-independent by design --
  a real, live-verified test (`test_distributed_spray_is_bounded_but_
  never_permanently_locks_the_account`) confirms a second, distinct source
  is also throttled immediately after a first source's attack, and that
  ordinary time advancement (never a special unlock) restores it.
- **Denial-of-service (against a real account):** no permanent lockout
  exists anywhere in this design -- the ladder plateaus at 60 seconds
  forever; a determined attacker can add bounded friction but can never
  deny a real user access indefinitely. Also considered and closed: the
  limiter's own internal state cannot grow without bound under a
  high-cardinality attack (see "Implementation").
- **Enumeration:** the public response (status code + body) is byte-
  identical across unknown-username, known-username-wrong-password, and
  throttled-known-username-even-with-the-correct-password -- see
  "Enumeration safety," below.
- **Local administrator recovery:** an owner who is ever throttled (whether
  by their own mistyping or an attack against their account) can restart
  the MockingBird process/service, which clears all in-memory throttle
  state immediately -- see "Design decision" for why this is deliberate,
  not a compromise.

## Design decision

**Account-keyed and source-keyed state, evaluated together; a request is
throttled if either currently says so.** Neither alone is sufficient (per
the governing brief's own explicit instruction not to rely on IP alone):
account-only cannot bound a username spray (each fake username starts its
own fresh counter); source-only cannot bound a distributed spray, and would
either trust a spoofable forwarded header (rejected -- no trusted-proxy
boundary exists) or collapse every legitimate user behind a shared address
into one bucket with no independent per-account protection at all.

**Delay/cooldown:** a short, fixed, hand-picked ladder --
`LOGIN_THROTTLE_FREE_ATTEMPTS = 3` (no delay at all for the first three
failures -- ordinary typo tolerance, and the exact number every pre-
existing test in `tests/test_local_identity_multi_user.py` that makes
multiple deliberately-wrong sign-in calls already stays within), then
`LOGIN_THROTTLE_DELAY_LADDER_SECONDS = (1.0, 2.0, 5.0, 15.0, 30.0, 60.0)`,
plateauing at 60 seconds forever. Deliberately **not** a copy of this
codebase's existing `ACOUSTIC_RETRY_BACKOFF_SECONDS`/`durable_supervisor`
retry ladders -- those exist to patiently recover an already-legitimate,
merely-flaky transport; this one exists to add friction for an adversary
while never asking a genuine person to wait more than a minute. The
*shape* (fixed ladder, hard plateau, never a formula) is deliberately
reused from that established convention; the *values* are a new,
first-of-its-kind, conservative choice for this specific domain, documented
directly in `mockingbird.security.login_rate_limiter`'s own module
docstring.

**Persistence: in-memory only.** Weighed explicitly against the governing
brief's own in-memory/persistent/hybrid framework:

| | In-memory (chosen) | Persistent (rejected) |
|---|---|---|
| Pros | Simple; automatically clears on restart; no schema change | Survives restart |
| Cons | Restart bypass | New schema/migration; clock-skew/timezone handling; **becomes its own persistent DoS surface** -- a throttle row that outlives the very restart an owner would use to recover |

A local-first appliance does not need enterprise-grade persistent lockout
state -- the realistic threat is an automated guesser hammering a *live*
process, which a transient in-process throttle already defeats for as long
as that process runs. "Restart bypass" is reframed, deliberately, as a
*feature* for this specific threat model: anyone with enough access to
restart the MockingBird process/service (or to trigger a local backup
restore, which already swaps the process-wide `ProductRepository` singleton
via `configure_repository` -- an existing, already-accepted precedent for
resetting exactly this class of in-memory session-adjacent state at that
same boundary) already has materially greater access than a remote/LAN
password-guesser -- they could already read the SQLite database file
directly. This makes restart a real, always-available, zero-new-code
recovery lever for an owner who is ever the one throttled, satisfying
"owner must retain a practical recovery path" without building any new
account-recovery mechanism (a deliberate non-goal). Verified directly
(`test_a_fresh_repository_has_no_memory_of_prior_throttle_state`): a fresh
`ProductRepository` against the identical on-disk database -- the user row
and its password survive, as expected; the throttle state does not.

**Clock:** monotonic (`time.monotonic`-shaped, constructor-injected as
`Callable[[], float]`), never wall-clock `datetime`, anywhere in the
throttle math -- immune to an NTP adjustment, a DST transition, or a
manually changed system clock. Mirrors this codebase's own established
`clock: Callable[[], datetime]` injection idiom (`AnalysisStreamRetryPolicy`,
`AcousticRuntime`, `durable_supervisor`), adapted to monotonic-float
semantics because the governing brief specifically calls for that. Every
test in both new test files injects a fake, manually-advanced clock --
zero real sleeps anywhere.

## Enumeration safety

The outward HTTP contract is **unchanged**: `POST /api/auth/sign-in`
returns the identical `401 {"detail": "Incorrect login identity or
password."}` for all four failure reasons -- unknown user, wrong password,
disabled user, and now, additionally, a currently-throttled account/source
(even when the password supplied is genuinely correct). No new status code
was introduced for throttling, so the "prove a differing status does not
create a username oracle" question does not arise -- there is no differing
status. A direct regression test
(`test_unknown_user_wrong_password_and_throttled_are_indistinguishable_
over_http`) compares all three cases' real HTTP responses (status code,
JSON body, and cookie absence) and asserts byte-for-byte equality.

The account-keyed throttle dimension itself is enumeration-safe by
construction: it is keyed by the raw normalized `login_identity` *string*,
never by a real `UserModel.id`, so a nonexistent username is tracked and
throttled exactly the same way as a real one (verified directly,
`test_nonexistent_account_key_is_throttled_exactly_like_a_real_one`).

**Honestly disclosed, not overclaimed:** a pre-existing (not introduced by
this milestone) timing characteristic remains -- an unknown-username
attempt returns before `hashlib.scrypt` is ever invoked (the original
`user is None` short-circuit, preserved verbatim), while a known-username-
wrong-password attempt pays one real scrypt hash. This milestone adds one
*further* timing distinction: a throttled attempt returns fastest of all
(no database query, no hashing at all). Per the governing brief's own
explicit instruction not to overclaim constant-time guarantees unless code
proves them: this code does not claim constant-time behavior, only that
the **response shape** (status + body) never reveals account existence.
The throttled-fast-path timing tell reveals only "this specific username/
source combination has now failed enough times to be throttled" -- a fact
the observer already caused by their own repeated attempts, not new
information about whether the account exists, since fake and real
usernames throttle identically.

## Implementation

**New module:** `src/mockingbird/security/login_rate_limiter.py` --
`LoginRateLimiter`, a small, dependency-free, thread-safe, in-process
helper (not a general-purpose rate-limiting framework). Two `OrderedDict`-
backed dimensions (account/source), kept in least-recently-touched order so
both stale-entry pruning and over-capacity eviction are O(1)-amortized
(caught and fixed during this milestone's own bounded-state tests -- an
earlier plain-`dict`-plus-`min()`-scan version made ~10,000 attempts take
several real seconds; the `OrderedDict` version makes the identical test
run in a small fraction of a second). Hard-capped at 10,000 live entries
per dimension.

**`ProductRepository` integration** (`src/mockingbird/repository/
product_repository.py`): one new optional constructor parameter,
`login_rate_limiter: LoginRateLimiter | None = None`, defaulting to a real
instance -- the identical dependency-injection seam already established for
`weather_requester`/`inaturalist_taxonomy_requester`. `authenticate_user`
gained one new optional keyword parameter, `source_ip: str | None = None`
(every pre-existing direct-repository-call test site keeps working
unchanged), and now: (1) calls `LoginRateLimiter.evaluate` before touching
the database at all -- a throttled attempt costs nothing beyond a dict
lookup; (2) on a real, verified failure, calls `record_failure` and writes
one bounded audit row (`auth.login_failed` or `auth.login_throttled`,
whichever the outcome warrants); (3) on a real, verified success, calls
`record_success` and, only if it just cleared a nonzero prior failure
count, writes one `auth.login_succeeded_after_failures` audit row. The
original short-circuit (`user is not None and user.enabled and verify_
password(...)`) is preserved exactly, so pre-existing timing/behavior for
unknown/disabled users is unchanged in shape.

**Endpoint** (`src/mockingbird/api/auth.py`): `sign_in` now extracts
`request.client.host` (the direct TCP peer address; `None` degrades to one
shared "unknown" source bucket, never to skipping the source dimension)
and passes it through. No other change to the endpoint's control flow,
status codes, or response shape.

No schema change. No new dependency. Confined to one new file plus two
small, precisely-scoped edits.

## Tests

**Tier 1 (focused, 67 tests, 0 failed):**

- `tests/test_login_rate_limiter.py` (new, 21 tests) -- pure unit coverage
  of `LoginRateLimiter` in isolation (no database, no HTTP, deterministic
  fake clock throughout): free-attempt tolerance; throttle activation;
  full ladder progression *and* plateau (proving no permanent/unbounded
  growth); time-advancement recovery; success clearing both dimensions
  (and proving the clear is genuine, not a partial decrement); username
  spray bounded by the source dimension; distributed spray bounded by the
  account dimension; independence when both differ; a nonexistent account
  key throttled identically to a real one; both dimensions' hard 10,000-key
  cap; opportunistic stale pruning (and proof it can never cut an active
  cooldown short); the real default clock; `normalize_source_key`'s edge
  cases.
- `tests/test_login_rate_limiting.py` (new, 10 tests) -- full product-
  integration suite through `ProductRepository.authenticate_user` and real
  `POST /api/auth/sign-in` HTTP calls (via `httpx.ASGITransport`'s own
  `client=(host, port)` parameter to simulate genuinely distinct source
  addresses): immediate success; a single failure creating no session; the
  enumeration-safety triple-comparison; repeated-same-account throttling
  blocking even the *correct* password; username spray over real HTTP;
  distributed spray across two simulated sources with no permanent lockout;
  success-after-failures clearing state and auditing recovery; the fresh-
  repository/"restart" persistence contract against the same on-disk
  database; a disabled user throttled like any other failure; the audit
  trail's exact event ordering/content with no secret leakage.
- `tests/test_local_identity_multi_user.py` (pre-existing, 36 tests, all
  still passing unmodified) -- direct regression proof that this milestone
  introduced no behavior change to bootstrap, sign-in/session lifecycle,
  authorization, review attribution, or backup/restore identity semantics.

**Tier 2 (376 tests across 26 files, 0 failed):** every directly auth/
security-adjacent file (`test_field_acceptance_authentication.py`,
`test_cors_security.py`, `test_windows_launcher_instance_identity.py`)
plus a deliberately broad, diverse cross-subsystem sample of the ~108
pre-existing files whose fixtures depend on `tests.conftest.
LegacyAuthenticatedTestClient`'s lazy bootstrap-then-sign-in succeeding
(camera/source setup and pairing, visit curation and Fast Review, bulk
review corrections, local backup/restore, storage retention, dashboard
truth, ecological export, webhook providers, species suggestions, acoustic
analysis, the upgrade-path acceptance suite, place story, motion, yard map,
the general API surface, single-app-runtime, and request-correlation/error-
handling). Zero failures anywhere -- direct, broad evidence that the one
call path every one of those ~108 files actually depends on (an ordinary,
first-attempt successful sign-in) is completely unaffected.

**Tier 3:** not run. The governing brief's own conditional bar --
"cross-cutting auth/session behavior changed, or repository evidence
indicates broad risk" -- is not met: the change is confined to one
repository method (`authenticate_user`), one endpoint (`sign_in`), and one
new, zero-existing-importers file; session *resolution*, authorization
tiers, and every other endpoint are untouched (confirmed by direct diff
inspection, not merely inferred). Tier 2's 376-test, 26-file result is
itself direct, broad, empirical confirmation of a narrow blast radius, not
just a scoping argument -- matching this codebase's own established
precedent for declining Tier 3 on a similarly bounded, non-cross-cutting
change (e.g. Local Only / Privacy Closure v1).

**`ruff check`:** clean (zero findings) on both new files
(`login_rate_limiter.py`, `test_login_rate_limiter.py`) and both touched
test/production files where new code was added
(`test_login_rate_limiting.py`, `auth.py`). `product_repository.py` itself
carries 57 pre-existing findings, confirmed -- via a direct `git stash
push -u`/`pop` bisection of exactly the files this milestone touched,
comparing the identical count and finding set before and after -- entirely
unrelated to this milestone's own diff (zero new findings in the ~3800-4300
and import-block line ranges this milestone actually edited).

## Audit/recovery behavior

Three new, narrow, bounded audit action names, written through the
existing `AuditLogEntryModel`/`record_audit_event` mechanism (zero schema
change, Administrator-readable via the existing `GET /api/admin/audit-log`,
capped at 500):

- `auth.login_failed` -- one real, verified credential failure that did not
  itself cross the throttle threshold. `target_id` is the real `user.id`
  when the account exists, `None` otherwise; `metadata` carries
  `login_identity`, `source_ip`, and both dimensions' current failure
  counts -- never a password.
- `auth.login_throttled` -- the specific failure that just activated
  throttling on either dimension (replaces, never duplicates, the
  `login_failed` event for that same attempt).
- `auth.login_succeeded_after_failures` -- a real success that cleared a
  nonzero prior failure count; `metadata` carries only the cleared count.

Bounded by construction, not by a separate suppression rule: an attempt
rejected purely because a throttle is *already* active never reaches
`authenticate_user`'s database/audit code at all (rejected by `evaluate`
before any of it), so an attacker spamming a throttled account/source
produces no additional audit rows -- audit volume is inherently capped by
the same ladder that bounds the attacks themselves. Verified directly
(`test_audit_log_records_failures_and_throttle_activation_with_no_secrets`):
exact event ordering, exact metadata content, and a direct assertion that
the real password used in the test never appears anywhere in the
serialized audit log, and that no entry's metadata ever carries a
`password` or `token` key.

**Recovery:** no new account-recovery mechanism was built (an explicit
non-goal). The existing supported recovery path for a forgotten password
(an Administrator's `POST /api/admin/users/{id}/reset-password`) is
untouched and unaffected by rate limiting -- an Administrator resetting
someone else's password is a different, already-authenticated code path
that never calls `authenticate_user` at all. For a *throttled* owner
specifically: restarting the MockingBird process/service clears all
throttle state immediately (see "Design decision").

## Remaining risks

Concrete only, each already disclosed in code/doc comments at its own
point of relevance:

- **Reverse-proxy source collapse.** A deployment behind an optional
  self-hosted reverse proxy sees every request from the proxy's own
  address, collapsing every user behind it into one shared source bucket.
  Deliberate (no trusted-proxy boundary exists for a forwarded header
  today); the account-keyed dimension remains the real, source-independent
  protection regardless.
- **Success-clears-shared-source trade-off.** A real success from a source
  clears that source's failure state too, not only the account that just
  succeeded, to avoid perpetually penalizing a shared legitimate address.
  Someone who already holds valid credentials for *some* account could
  exploit this to keep a source-level spray against *other* accounts
  perpetually reset -- bounded by this product having no self-service
  account creation (already requires possessing a real credential first).
- **Non-atomic evaluate-then-record.** Two fully concurrent requests can
  both pass `evaluate` before either calls `record_failure`/`record_
  success` -- a narrow, bounded, self-correcting-on-the-next-request
  timing imprecision under true concurrency, never a crash, corruption, or
  permanent bypass.
- **Pre-existing, not newly introduced:** the unknown-user-vs-known-user
  scrypt timing distinction (see "Enumeration safety").
- **In-memory persistence means a process restart clears throttle state**
  -- a deliberate design decision (see "Design decision"), not an
  oversight, but worth restating plainly here as a real, if intentional,
  boundary: an attacker who can force/await a restart also resets their
  own throttle. Judged acceptable because that level of access already
  exceeds what pure remote credential-guessing requires.

## Decision

**Classification A.**

- Real pre-fix absence of rate limiting established by direct code
  archaeology (zero rate-limit/throttle/lockout/attempt patterns anywhere
  in the auth path) and cross-referenced against three independent prior
  disclosures.
- Repeated guessing against one account is bounded (progressive ladder,
  verified end to end including blocking the genuinely correct password
  while throttled).
- Username spray is bounded (source dimension, verified over real HTTP).
- No permanent lockout anywhere (ladder plateaus; time advancement always
  restores access; verified for both single- and multi-source attacks).
- Outward failures remain enumeration-safe (byte-identical response across
  all three cases, verified directly; no new status code introduced).
- Legitimate success always recovers immediately, clears state, and is not
  delayed by stale failures.
- Limiter state is bounded in both memory and CPU (hard cap + O(1)-
  amortized eviction/pruning; the earlier O(n)-scan inefficiency was found
  and fixed by this milestone's own tests before being accepted).
- No session is ever created on a failed or throttled attempt (verified
  directly against real session-table row counts).
- No password/token leakage anywhere in the new audit trail (verified
  directly).
- Localhost/LAN/remote behavior is deliberate and documented (no blind
  localhost exemption; no trust placed in an unestablished forwarded-header
  boundary; the account dimension remains protective regardless of source
  topology).
- Tier 1 clean (67/67), Tier 2 clean (376/376 across 26 files); Tier 3
  deliberately not run, with the narrow-blast-radius reasoning stated
  explicitly above rather than assumed.
