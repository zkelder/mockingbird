"""Bounded, in-memory login abuse-resistance state (Login Rate-Limiting &
Authentication Abuse Resistance v1; see docs/local-identity-multi-user-
contract.md "Login rate limiting").

Human login (`ProductRepository.authenticate_user`) previously had generic,
enumeration-safe failure behavior (unknown user / wrong password / disabled
user all returned the identical `None`) but no attempt counting, no delay,
and no throttling at all -- confirmed by direct archaeology (zero rate-limit/
throttle/lockout/attempt patterns anywhere in `mockingbird.api.auth` or
`mockingbird.repository.product_repository` before this module), and already
disclosed as a real, pre-existing gap by Mobile & Remote Experience v1's own
security review. This module closes that gap with the smallest coherent
mechanism: a small, standalone, dependency-free helper -- not a new
general-purpose rate-limiting framework -- that `ProductRepository` owns one
instance of, mirroring how it already owns `_administrator_bootstrap_lock`/
`_observation_authority_lock` as plain in-process state.

**Persistence decision: in-memory only, never written to the database.**
Considered explicitly against this milestone's own governing brief:

* A local-first appliance-class product does not need enterprise-grade
  persistent lockout state -- the realistic threat here is an automated
  guesser hammering a live process, which a transient in-process throttle
  already defeats while that process is running.
* Persisting throttle state would need its own schema/migration, its own
  clock-skew/timezone handling, and -- worse -- would itself become a new
  persistent denial-of-service surface (an attacker's throttle rows would
  outlive the very process restart an owner would otherwise use to recover).
* Resetting on restart is a *feature*, not a compromise, for this threat
  model: anyone with enough access to restart the MockingBird process/
  service (or to trigger a local backup restore, which already swaps the
  process-wide `ProductRepository` singleton via `configure_repository` --
  see "Backup/restore identity semantics" in the governing contract, an
  already-established precedent for exactly this kind of in-memory
  session-adjacent state resetting on that same boundary) already has
  materially greater access than a remote/LAN password-guesser -- they could
  already read the SQLite database file directly. Restart is therefore
  always available to an owner as a real, zero-new-code recovery lever if
  they are ever the one throttled.

**Clock:** monotonic (`time.monotonic`-shaped, injected as a `Callable[[],
float]`), never wall-clock `datetime`. Delay/cooldown math must never be
disturbed by an NTP adjustment, DST transition, or a user manually changing
the system clock -- see this milestone's own governing brief, "Clock /
timing." Tests inject a fake, deterministic, manually-advanced clock instead
of sleeping for real seconds (`LoginRateLimiter(clock=fake_clock)`) --
mirrors this codebase's own established `clock: Callable[[], datetime]`
constructor-injection idiom (`AnalysisStreamRetryPolicy`, `AcousticRuntime`,
`durable_supervisor`), adapted to monotonic-float semantics here because the
brief specifically calls for that, not wall-clock semantics.

**Two independent keyed dimensions**, evaluated together, per the governing
brief's own explicit guidance not to rely on IP alone:

* **Account-keyed** (`login_identity`, normalized lowercase, *whether or not
  it names a real user* -- see "Enumeration safety" below): bounds repeated
  guessing against one specific account regardless of source.
* **Source-keyed** (the direct TCP peer address, `request.client.host` --
  never a `X-Forwarded-For`-style header; this deployment establishes no
  trusted-proxy boundary for that header anywhere today, see `mockingbird.
  api.auth._request_is_secure`'s own docstring for the one, narrower,
  already-accepted exception for `X-Forwarded-Proto` on a cookie attribute
  only, never an authorization/throttling decision): bounds a spray of many
  different usernames from one source.

A request is throttled if *either* dimension currently says so. This
combination is what stops a username spray (one source, many accounts, each
individually under any single-account threshold) without needing to trust
network topology, and what stops sustained guessing against one account from
many sources (distributed spray) without collapsing every legitimate
multi-user household/office behind one address into a single bucket.

**Enumeration safety:** the account dimension is keyed by the raw
normalized `login_identity` *string*, not by a real `UserModel.id` -- an
attempt against a nonexistent username is tracked and throttled exactly the
same way as one against a real username. Combined with `authenticate_user`
returning the identical `None` for "throttled" as for "wrong password" (see
its own docstring), a caller cannot distinguish "this account does not
exist" from "this account exists but you guessed wrong" from "you are
temporarily throttled" by response shape alone.

**No permanent lockout:** the delay ladder is bounded and plateaus at its
last rung forever -- it never grows without bound and never blocks
indefinitely. A real, patient owner (or a legitimate user who mistyped a
password several times) always regains access by simply waiting out the
current (bounded, short) cooldown; nothing here can lock a real account out
permanently.

**Bounded memory (and CPU):** both dimensions are capped at `LOGIN_
THROTTLE_MAX_TRACKED_KEYS` live entries, least-recently-touched-first
eviction beyond the cap, plus opportunistic pruning of anything idle longer
than `LOGIN_THROTTLE_STALE_ENTRY_AGE_SECONDS` -- both O(1)-amortized (an
`OrderedDict` kept in touch-order, never a `min()`/full-table scan) so a
high-rate distributed attacker spraying unbounded distinct usernames/
sources costs this process only a small, fixed amount of memory and no
growing per-attempt CPU cost either.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

# A small, first-of-its-kind ladder for this specific domain -- deliberately
# *not* a copy of `ACOUSTIC_RETRY_BACKOFF_SECONDS`/`durable_supervisor`'s own
# retry ladders. Those exist to patiently recover an already-legitimate,
# merely-flaky transport (a real Camera Node that will reconnect); this one
# exists to add friction for an adversary and must stay short enough that a
# real person who mistyped their own password is never made to wait minutes.
# The *shape* (a short, fixed, hand-picked ladder rather than a formula, with
# a hard plateau rather than unbounded growth) is deliberately reused from
# that established convention -- see `_apply_acoustic_retry_decision`'s own
# docstring for why this codebase already prefers fixed ladders over
# exponential formulas. Conservative and appropriate for a local appliance:
#
# * The first `LOGIN_THROTTLE_FREE_ATTEMPTS` failures in a row add no delay
#   at all -- ordinary typo tolerance, matching every pre-existing test in
#   `tests/test_local_identity_multi_user.py` that already makes up to three
#   deliberately-wrong sign-in calls in a row with no throttle expected.
# * Every failure after that walks one rung further down the ladder, up to
#   60 seconds -- meaningful, bounded friction against automated guessing
#   (combined with the real per-guess `hashlib.scrypt` cost already paid on
#   every attempt that reaches credential verification at all -- see
#   `mockingbird.security.passwords`) without ever asking a genuine person
#   to wait more than a minute between retries.
LOGIN_THROTTLE_FREE_ATTEMPTS = 3
LOGIN_THROTTLE_DELAY_LADDER_SECONDS: tuple[float, ...] = (1.0, 2.0, 5.0, 15.0, 30.0, 60.0)

#: An entry idle longer than this is pruned on the next write to either
#: dimension -- comfortably longer than the ladder's own 60-second plateau,
#: so pruning can never cut a real cooldown short.
LOGIN_THROTTLE_STALE_ENTRY_AGE_SECONDS = 3600.0

#: Hard cap on live entries per dimension. Generous for any real single-
#: household/office deployment (a handful of accounts, a handful of source
#: addresses) while still bounding worst-case memory for a high-rate,
#: high-cardinality distributed attacker to a small, fixed footprint.
LOGIN_THROTTLE_MAX_TRACKED_KEYS = 10_000

#: The source key used whenever no real client address is available (a
#: malformed/absent ASGI `client` tuple). Deliberately one shared bucket --
#: not "no throttling" -- so this path still degrades safely rather than
#: silently bypassing the source dimension entirely.
UNKNOWN_SOURCE_KEY = "unknown"


@dataclass
class _AttemptState:
    failure_count: int = 0
    throttled_until: float | None = None
    last_activity_at: float = 0.0


@dataclass(frozen=True)
class LoginThrottleDecision:
    """The outcome of `LoginRateLimiter.evaluate` -- call *before* touching
    the database or verifying a password. `throttled_by_account`/`_source`
    are for internal diagnostics/audit metadata only; the public HTTP
    contract must never expose which dimension fired (see the governing
    contract's "Login rate limiting" -- a uniform outward failure)."""

    throttled: bool
    retry_after_seconds: float = 0.0
    throttled_by_account: bool = False
    throttled_by_source: bool = False


@dataclass(frozen=True)
class LoginAttemptOutcome:
    """The outcome of `LoginRateLimiter.record_failure`."""

    newly_throttled: bool
    account_failure_count: int
    source_failure_count: int


class LoginRateLimiter:
    """Small, dependency-free, thread-safe login-attempt throttle. One
    instance is owned by `ProductRepository` for the lifetime of the
    process (see its own constructor) -- never a module-level singleton, so
    each `ProductRepository` (including a fresh one built by test fixtures,
    or the one that replaces the process-wide singleton after a backup
    restore) starts with a clean slate, matching the in-memory persistence
    decision documented in this module's own docstring.

    Every public method takes its own short critical section under one
    coarse lock, matching this codebase's established in-process-locking
    style elsewhere in `ProductRepository` -- correct for this product's
    single-process, local-first runtime, not a claim of cross-process
    safety.
    """

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._lock = threading.Lock()
        # `OrderedDict`, not a plain `dict`: `_get_or_create_locked` below
        # keeps insertion order equal to least-recently-touched-first order
        # (via `move_to_end` on every touch), which turns both "prune the
        # stale entries at the front" and "evict the single oldest entry
        # once at capacity" into O(1)-amortized operations instead of an
        # O(n) full-table scan on every single attempt -- see `test_login_
        # rate_limiter.py`'s own bounded-state tests, which caught this
        # scan cost directly (~10,000 attempts took several real seconds
        # with a plain-`dict`-plus-`min()` implementation; this codebase's
        # own "high-rate attacker must not cause unlimited memory growth"
        # bar reasonably extends to "must not cause unbounded *CPU* growth
        # either").
        self._account_state: OrderedDict[str, _AttemptState] = OrderedDict()
        self._source_state: OrderedDict[str, _AttemptState] = OrderedDict()

    @staticmethod
    def normalize_source_key(source_ip: str | None) -> str:
        stripped = source_ip.strip() if source_ip else ""
        return stripped or UNKNOWN_SOURCE_KEY

    @property
    def account_key_count(self) -> int:
        """Live account-dimension entry count -- exposed only for bounded-
        state regression tests (see `tests/test_login_rate_limiter.py`)."""

        with self._lock:
            return len(self._account_state)

    @property
    def source_key_count(self) -> int:
        """Live source-dimension entry count -- same purpose as
        `account_key_count` above."""

        with self._lock:
            return len(self._source_state)

    def evaluate(self, *, account_key: str, source_key: str) -> LoginThrottleDecision:
        """Whether this attempt is currently throttled by either dimension.
        Read-only -- never mutates state, never itself counts as an
        attempt. Call this before any database/credential-verification work
        so a known-throttled request costs nothing beyond a dict lookup."""

        now = self._clock()
        with self._lock:
            account_retry = self._remaining_seconds_locked(self._account_state.get(account_key), now)
            source_retry = self._remaining_seconds_locked(self._source_state.get(source_key), now)
        retry_after = max(account_retry, source_retry)
        if retry_after <= 0.0:
            return LoginThrottleDecision(throttled=False)
        return LoginThrottleDecision(
            throttled=True,
            retry_after_seconds=retry_after,
            throttled_by_account=account_retry > 0.0,
            throttled_by_source=source_retry > 0.0,
        )

    @staticmethod
    def _remaining_seconds_locked(state: _AttemptState | None, now: float) -> float:
        if state is None or state.throttled_until is None:
            return 0.0
        return max(0.0, state.throttled_until - now)

    def record_failure(self, *, account_key: str, source_key: str) -> LoginAttemptOutcome:
        """Record one real, verified authentication failure (never call
        this for an attempt `evaluate` already reported as throttled --
        that attempt never reached credential verification at all, and
        recording it again would double-count). Updates both dimensions
        from the same single attempt and returns the resulting counts plus
        whether this specific failure is the one that just activated
        throttling on either dimension (used to choose the audit action
        name -- see `ProductRepository.authenticate_user`)."""

        now = self._clock()
        with self._lock:
            account_state = self._get_or_create_locked(self._account_state, account_key, now)
            source_state = self._get_or_create_locked(self._source_state, source_key, now)
            account_state.failure_count += 1
            source_state.failure_count += 1
            account_state.last_activity_at = now
            source_state.last_activity_at = now
            account_newly_throttled = self._apply_throttle_locked(account_state, now)
            source_newly_throttled = self._apply_throttle_locked(source_state, now)
            return LoginAttemptOutcome(
                newly_throttled=account_newly_throttled or source_newly_throttled,
                account_failure_count=account_state.failure_count,
                source_failure_count=source_state.failure_count,
            )

    @staticmethod
    def _apply_throttle_locked(state: _AttemptState, now: float) -> bool:
        if state.failure_count <= LOGIN_THROTTLE_FREE_ATTEMPTS:
            return False
        rung = state.failure_count - LOGIN_THROTTLE_FREE_ATTEMPTS - 1
        delay_seconds = LOGIN_THROTTLE_DELAY_LADDER_SECONDS[
            min(rung, len(LOGIN_THROTTLE_DELAY_LADDER_SECONDS) - 1)
        ]
        was_already_throttled = state.throttled_until is not None and state.throttled_until > now
        state.throttled_until = now + delay_seconds
        return not was_already_throttled

    def record_success(self, *, account_key: str, source_key: str) -> int:
        """Record one real, verified authentication success. Clears both
        dimensions' failure state outright (a fresh entry is lazily
        recreated only on a future failure) and returns the account
        dimension's failure count immediately before this clear (`0` if
        there were no prior failures) -- the caller uses this to decide
        whether a "succeeded after failures" audit event is warranted.

        Clearing the *source* dimension too (not only the account that just
        succeeded) is a deliberate choice: the governing brief explicitly
        warns against over-penalizing multiple legitimate users/accounts
        behind one shared address (a household LAN, an optional reverse
        proxy) -- a real success from that source is the strongest signal
        available that the source itself is not purely adversarial right
        now. The disclosed, accepted trade-off: someone who already holds
        valid credentials for *some* account could exploit this to keep a
        source-level spray against *other* accounts perpetually reset. This
        product has no self-service account creation (every account is
        Administrator-provisioned), so exploiting this already requires
        already possessing a real credential -- a fundamentally smaller,
        different threat than unauthenticated remote guessing, and not one
        this milestone's bounded scope treats as equivalent.
        """

        with self._lock:
            account_state = self._account_state.pop(account_key, None)
            self._source_state.pop(source_key, None)
            return account_state.failure_count if account_state is not None else 0

    def _get_or_create_locked(
        self, table: OrderedDict[str, _AttemptState], key: str, now: float
    ) -> _AttemptState:
        state = table.get(key)
        if state is not None:
            table.move_to_end(key)  # mark most-recently-touched, for O(1) LRU pruning/eviction below
            return state
        self._prune_stale_locked(table, now)
        if len(table) >= LOGIN_THROTTLE_MAX_TRACKED_KEYS:
            table.popitem(last=False)  # evict the single least-recently-touched entry, O(1)
        state = _AttemptState(last_activity_at=now)
        table[key] = state
        return state

    @staticmethod
    def _prune_stale_locked(table: OrderedDict[str, _AttemptState], now: float) -> None:
        """Remove every entry idle longer than `LOGIN_THROTTLE_STALE_ENTRY_
        AGE_SECONDS`, cheaply. `table` is kept in least-recently-touched-
        first order (see `_get_or_create_locked`'s own `move_to_end`), so
        the stale entries -- if any -- are always exactly the ones at the
        front; this stops at the first still-fresh entry rather than
        scanning the whole table on every call."""

        while table:
            oldest_key = next(iter(table))
            if (now - table[oldest_key].last_activity_at) <= LOGIN_THROTTLE_STALE_ENTRY_AGE_SECONDS:
                break
            del table[oldest_key]
