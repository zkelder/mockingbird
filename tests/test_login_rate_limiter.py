"""Login Rate-Limiting & Authentication Abuse Resistance v1 -- pure unit
tests for `LoginRateLimiter` in isolation (no database, no HTTP, no real
sleeps -- a fake, manually-advanced monotonic clock throughout, per the
governing brief's own "Clock / timing" requirement). See
tests/test_login_rate_limiting.py for the full product-integration suite
through `ProductRepository.authenticate_user` and real
`POST /api/auth/sign-in` HTTP calls.
"""

from __future__ import annotations

import pytest

from mockingbird.security.login_rate_limiter import (
    LOGIN_THROTTLE_DELAY_LADDER_SECONDS,
    LOGIN_THROTTLE_FREE_ATTEMPTS,
    LOGIN_THROTTLE_MAX_TRACKED_KEYS,
    LOGIN_THROTTLE_STALE_ENTRY_AGE_SECONDS,
    LoginRateLimiter,
)


class FakeClock:
    """Deterministic, manually-advanced monotonic-shaped clock."""

    def __init__(self, start: float = 1_000.0) -> None:
        self._now = start

    def __call__(self) -> float:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def limiter(clock: FakeClock) -> LoginRateLimiter:
    return LoginRateLimiter(clock=clock)


# --- Free attempts / throttle activation ------------------------------------


def test_free_attempts_add_no_delay(limiter: LoginRateLimiter) -> None:
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS):
        outcome = limiter.record_failure(account_key="ada", source_key="1.2.3.4")
        assert outcome.newly_throttled is False
    decision = limiter.evaluate(account_key="ada", source_key="1.2.3.4")
    assert decision.throttled is False


def test_failure_beyond_free_attempts_activates_throttle(limiter: LoginRateLimiter) -> None:
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS):
        limiter.record_failure(account_key="ada", source_key="1.2.3.4")
    outcome = limiter.record_failure(account_key="ada", source_key="1.2.3.4")
    assert outcome.newly_throttled is True
    decision = limiter.evaluate(account_key="ada", source_key="1.2.3.4")
    assert decision.throttled is True
    assert decision.retry_after_seconds == pytest.approx(LOGIN_THROTTLE_DELAY_LADDER_SECONDS[0])
    assert decision.throttled_by_account is True
    assert decision.throttled_by_source is True  # same single source made every attempt


# --- Progressive delay / no permanent lockout --------------------------------


def test_delay_ladder_progresses_then_plateaus_at_its_last_rung(
    limiter: LoginRateLimiter, clock: FakeClock
) -> None:
    """Drives well past the ladder's own length. The delay must climb the
    ladder exactly, then plateau forever at its last rung -- never grow
    unbounded, never become permanent."""

    # The first `LOGIN_THROTTLE_FREE_ATTEMPTS` failures add no delay at all
    # (typo tolerance) -- burn through those first, unobserved, exactly like
    # `test_free_attempts_add_no_delay` already covers on its own.
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS):
        limiter.record_failure(account_key="ada", source_key="1.2.3.4")

    observed_delays: list[float] = []
    throttled_failures = len(LOGIN_THROTTLE_DELAY_LADDER_SECONDS) + 3
    for _ in range(throttled_failures):
        limiter.record_failure(account_key="ada", source_key="1.2.3.4")
        decision = limiter.evaluate(account_key="ada", source_key="1.2.3.4")
        assert decision.throttled is True
        observed_delays.append(decision.retry_after_seconds)
        clock.advance(decision.retry_after_seconds)  # simulate waiting the cooldown out exactly

    assert observed_delays[: len(LOGIN_THROTTLE_DELAY_LADDER_SECONDS)] == list(
        LOGIN_THROTTLE_DELAY_LADDER_SECONDS
    )
    assert all(
        delay == LOGIN_THROTTLE_DELAY_LADDER_SECONDS[-1]
        for delay in observed_delays[len(LOGIN_THROTTLE_DELAY_LADDER_SECONDS) :]
    )


def test_time_advancement_past_cooldown_restores_access(
    limiter: LoginRateLimiter, clock: FakeClock
) -> None:
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 1):
        limiter.record_failure(account_key="ada", source_key="1.2.3.4")
    decision = limiter.evaluate(account_key="ada", source_key="1.2.3.4")
    assert decision.throttled is True

    clock.advance(decision.retry_after_seconds + 0.01)

    assert limiter.evaluate(account_key="ada", source_key="1.2.3.4").throttled is False


# --- Success reset ------------------------------------------------------------


def test_success_clears_account_and_source_failure_state(limiter: LoginRateLimiter) -> None:
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS):
        limiter.record_failure(account_key="ada", source_key="1.2.3.4")

    cleared = limiter.record_success(account_key="ada", source_key="1.2.3.4")

    assert cleared == LOGIN_THROTTLE_FREE_ATTEMPTS
    assert limiter.account_key_count == 0
    assert limiter.source_key_count == 0
    assert limiter.evaluate(account_key="ada", source_key="1.2.3.4").throttled is False


def test_success_with_no_prior_failures_returns_zero(limiter: LoginRateLimiter) -> None:
    assert limiter.record_success(account_key="ada", source_key="1.2.3.4") == 0


def test_state_is_genuinely_cleared_not_merely_decremented(limiter: LoginRateLimiter) -> None:
    """After a clean success, a fresh round of failures must need the full
    free-attempts budget again before throttling -- proving `record_success`
    truly resets state rather than leaving a residual count behind."""

    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS):
        limiter.record_failure(account_key="ada", source_key="1.2.3.4")
    limiter.record_success(account_key="ada", source_key="1.2.3.4")

    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS):
        outcome = limiter.record_failure(account_key="ada", source_key="1.2.3.4")
        assert outcome.newly_throttled is False


# --- Two independent dimensions -----------------------------------------------


def test_username_spray_from_one_source_is_bounded_by_source_dimension(
    limiter: LoginRateLimiter,
) -> None:
    """Many distinct (nonexistent) usernames, each individually under its
    own account-level free-attempts budget, still get bounded together by
    the shared source dimension."""

    outcome = None
    for index in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 2):
        outcome = limiter.record_failure(account_key=f"fake-user-{index}", source_key="10.0.0.5")
    assert outcome is not None
    assert outcome.source_failure_count == LOGIN_THROTTLE_FREE_ATTEMPTS + 2

    # A brand new username, never tried before, from the same source.
    decision = limiter.evaluate(account_key="yet-another-fake-user", source_key="10.0.0.5")
    assert decision.throttled is True
    assert decision.throttled_by_source is True
    assert decision.throttled_by_account is False


def test_distributed_spray_against_one_account_is_bounded_by_account_dimension(
    limiter: LoginRateLimiter,
) -> None:
    """Many distinct sources, each individually under its own source-level
    free-attempts budget, still get bounded together against one shared
    account by the account dimension."""

    for index in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 2):
        limiter.record_failure(account_key="ada", source_key=f"203.0.113.{index}")

    decision = limiter.evaluate(account_key="ada", source_key="198.51.100.99")  # a brand new source
    assert decision.throttled is True
    assert decision.throttled_by_account is True
    assert decision.throttled_by_source is False


def test_accounts_and_sources_are_independent_when_both_differ(limiter: LoginRateLimiter) -> None:
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 1):
        limiter.record_failure(account_key="ada", source_key="1.1.1.1")
    assert limiter.evaluate(account_key="bea", source_key="2.2.2.2").throttled is False


# --- Enumeration-safety-adjacent: unknown vs. real account keys identically ---


def test_nonexistent_account_key_is_throttled_exactly_like_a_real_one(
    limiter: LoginRateLimiter,
) -> None:
    """The limiter has no concept of "real" vs "fake" account -- it only
    ever sees the normalized login-identity string. Confirms both are
    tracked/throttled by the identical code path (never a special case)."""

    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 1):
        limiter.record_failure(account_key="totally-nonexistent-user", source_key="7.7.7.7")
    decision = limiter.evaluate(account_key="totally-nonexistent-user", source_key="7.7.7.7")
    assert decision.throttled is True
    assert decision.retry_after_seconds == pytest.approx(LOGIN_THROTTLE_DELAY_LADDER_SECONDS[0])


# --- Bounded memory / DoS resistance ------------------------------------------


def test_account_dimension_is_bounded_by_max_tracked_keys(limiter: LoginRateLimiter) -> None:
    for index in range(LOGIN_THROTTLE_MAX_TRACKED_KEYS + 50):
        limiter.record_failure(account_key=f"user-{index}", source_key="1.2.3.4")
    assert limiter.account_key_count <= LOGIN_THROTTLE_MAX_TRACKED_KEYS


def test_source_dimension_is_bounded_by_max_tracked_keys(limiter: LoginRateLimiter) -> None:
    for index in range(LOGIN_THROTTLE_MAX_TRACKED_KEYS + 50):
        limiter.record_failure(account_key="ada", source_key=f"10.{index // 65536}.{(index // 256) % 256}.{index % 256}")
    assert limiter.source_key_count <= LOGIN_THROTTLE_MAX_TRACKED_KEYS


def test_stale_entries_are_pruned_after_the_stale_age(
    limiter: LoginRateLimiter, clock: FakeClock
) -> None:
    limiter.record_failure(account_key="ada", source_key="1.2.3.4")
    assert limiter.account_key_count == 1

    clock.advance(LOGIN_THROTTLE_STALE_ENTRY_AGE_SECONDS + 1.0)
    limiter.record_failure(account_key="someone-else", source_key="9.9.9.9")  # triggers opportunistic pruning

    assert limiter.account_key_count == 1  # "ada" pruned as stale; only "someone-else" remains
    assert limiter.evaluate(account_key="ada", source_key="1.2.3.4").throttled is False


def test_stale_pruning_never_cuts_an_active_cooldown_short(
    limiter: LoginRateLimiter, clock: FakeClock
) -> None:
    """The stale-entry age is deliberately longer than the ladder's own
    plateau -- an entry can never be pruned while it is still genuinely
    throttled."""

    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 1):
        limiter.record_failure(account_key="ada", source_key="1.2.3.4")
    assert LOGIN_THROTTLE_STALE_ENTRY_AGE_SECONDS > LOGIN_THROTTLE_DELAY_LADDER_SECONDS[-1]


# --- Clock injection -----------------------------------------------------------


def test_default_clock_is_real_monotonic_time() -> None:
    import time

    started_at = time.monotonic()
    limiter = LoginRateLimiter()
    for _ in range(LOGIN_THROTTLE_FREE_ATTEMPTS + 1):
        limiter.record_failure(account_key="ada", source_key="1.2.3.4")
    decision = limiter.evaluate(account_key="ada", source_key="1.2.3.4")
    elapsed = time.monotonic() - started_at

    # With no clock injected, the real default (`time.monotonic`) is used --
    # the reported cooldown matches the first ladder rung (real elapsed test
    # time is negligible at this scale), and this whole check completes
    # near-instantly -- no real sleep anywhere in this module.
    assert decision.retry_after_seconds == pytest.approx(LOGIN_THROTTLE_DELAY_LADDER_SECONDS[0], abs=1.0)
    assert elapsed < 1.0


# --- Normalize source key -------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, "unknown"),
        ("", "unknown"),
        ("   ", "unknown"),
        (" 10.0.0.1 ", "10.0.0.1"),
        ("203.0.113.7", "203.0.113.7"),
    ],
)
def test_normalize_source_key(raw: str | None, expected: str) -> None:
    assert LoginRateLimiter.normalize_source_key(raw) == expected
