"""Local password hashing (Local Identity, Multi-User & Organization Access
v1; see docs/local-identity-multi-user-contract.md "Identity contract").

Uses the Python standard library's `hashlib.scrypt` (RFC 7914) rather than
a third-party dependency (`bcrypt`/`argon2-cffi`/`passlib`). Confirmed via
direct archaeology that none of those are installed or importable in this
project's `.venv`, and that this project has repeatedly hit real, costly
compiled-wheel problems getting dependencies onto its packaged Windows
build (see e.g. docs/windows-onnxruntime-cuda-dll-loading, the pinned
`onnxruntime-gpu`/CUDA wheel matrix in pyproject.toml's optional
dependencies). `hashlib.scrypt` needs no new wheel on any platform this
project ships to -- it has been part of CPython's standard library (built
against the system/bundled OpenSSL) since 3.6. This is not "inventing
cryptography": scrypt is a standardized (RFC 7914), widely reviewed
password-hashing KDF, and the parameters below sit within OWASP's
documented acceptable range for interactive login.

Nothing plaintext is ever persisted. The stored string is self-describing
(`scrypt$n=..,r=..,p=..$<salt_hex>$<hash_hex>`) specifically so a future
change to the cost parameters (or even the algorithm) can detect an
old-format hash and transparently re-hash it on the next successful login,
without a schema migration or a bulk rewrite of `users.password_hash`.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets

# OWASP Password Storage Cheat Sheet's scrypt guidance lists N=2**15 (32768),
# r=8, p=1 (~128 MiB) as an acceptable middle tier for an interactive login
# path -- strong enough to make offline brute-forcing of a stolen hash
# expensive, without imposing a multi-second cost on a local appliance-class
# Host that may be modest hardware (see docs/local-identity-multi-user-
# contract.md "Local network security guidance").
_SCRYPT_N = 2**15
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SALT_BYTES = 16
# `hashlib.scrypt`'s actual working-memory requirement is ~128*n*r bytes
# (32 MiB for the parameters above) -- but CPython's OpenSSL binding
# refuses to run unless `maxmem` is passed and is large enough to cover
# it, defaulting to a conservative 32 MiB cap that this exact parameter
# set already exceeds in practice (confirmed by direct execution: a bare
# call with no `maxmem` raises "memory limit exceeded" here). This is a
# generous fixed ceiling, not tied precisely to `_SCRYPT_N`/`_SCRYPT_R`,
# so tuning those later doesn't also require re-deriving this value --
# comfortable headroom on any machine this Host realistically runs on.
_SCRYPT_MAXMEM = 128 * 1024 * 1024

_ALGORITHM_TAG = "scrypt"

# NIST SP 800-63B favors length over composition rules; no uppercase/digit/
# symbol requirements are enforced. An upper bound exists only to keep
# `hashlib.scrypt`'s cost bounded against a pathological input, not as a
# usability constraint.
MINIMUM_PASSWORD_LENGTH = 10
MAXIMUM_PASSWORD_LENGTH = 256


class WeakPasswordError(ValueError):
    """Raised when a candidate password fails the minimum local policy."""


def validate_password_strength(password: str) -> None:
    """Enforce the one bounded local password policy: length only.

    Raises `WeakPasswordError` (a `ValueError`) with a message safe to
    surface directly to a user (never includes the password itself).
    """

    if len(password) < MINIMUM_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Password must be at least {MINIMUM_PASSWORD_LENGTH} characters long."
        )
    if len(password) > MAXIMUM_PASSWORD_LENGTH:
        raise WeakPasswordError(
            f"Password must be no more than {MAXIMUM_PASSWORD_LENGTH} characters long."
        )


def hash_password(password: str) -> str:
    """Hash `password` for durable storage in `UserModel.password_hash`.

    Does not itself enforce `validate_password_strength` -- callers (the
    sign-up/reset/change-password repository methods) run that check first
    so a rejected weak password never reaches this function at all.
    """

    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN, maxmem=_SCRYPT_MAXMEM,
    )
    return (
        f"{_ALGORITHM_TAG}$n={_SCRYPT_N},r={_SCRYPT_R},p={_SCRYPT_P}"
        f"${salt.hex()}${derived.hex()}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Constant-time-compare `password` against a `hash_password` output.

    Returns `False` (never raises) for a malformed/unrecognized stored
    hash, including one whose embedded cost parameters `hashlib.scrypt`
    itself refuses (e.g. exceeding `_SCRYPT_MAXMEM`) -- a corrupt or
    adversarial row must fail closed, not become a 500.
    """

    try:
        algorithm, params, salt_hex, hash_hex = stored_hash.split("$")
        if algorithm != _ALGORITHM_TAG:
            return False
        parsed = dict(item.split("=", 1) for item in params.split(","))
        n, r, p = int(parsed["n"]), int(parsed["r"]), int(parsed["p"])
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        candidate = hashlib.scrypt(
            password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
            dklen=len(expected), maxmem=_SCRYPT_MAXMEM,
        )
    except (ValueError, KeyError):
        return False
    return hmac.compare_digest(candidate, expected)


def needs_rehash(stored_hash: str) -> bool:
    """Whether `stored_hash` was produced with weaker-than-current
    parameters (or is otherwise not today's format) and should be
    silently replaced the next time the plaintext is available (i.e. right
    after a successful `verify_password`)."""

    try:
        algorithm, params, _salt_hex, _hash_hex = stored_hash.split("$")
        if algorithm != _ALGORITHM_TAG:
            return True
        parsed = dict(item.split("=", 1) for item in params.split(","))
        return not (
            int(parsed["n"]) >= _SCRYPT_N
            and int(parsed["r"]) >= _SCRYPT_R
            and int(parsed["p"]) >= _SCRYPT_P
        )
    except (ValueError, KeyError):
        return True


def generate_session_token() -> str:
    """A high-entropy opaque session token for a Set-Cookie value -- see
    `UserSessionModel`'s docstring for why only its hash is ever stored."""

    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Deterministic, one-way lookup key for a session token. Plain SHA-256
    (not scrypt) is deliberate and correct here: unlike a password, this
    input already has 256 bits of real entropy from `secrets.token_urlsafe`,
    so it needs no deliberately-slow KDF -- a fast hash is what makes an
    O(1) session lookup on every request affordable, exactly like an API
    key or bearer-token hash in any established auth library."""

    return hashlib.sha256(token.encode("utf-8")).hexdigest()
