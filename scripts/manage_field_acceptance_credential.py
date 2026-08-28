#!/usr/bin/env python3
"""Non-Interactive Field Acceptance Authentication & Session Access v1: a
bounded administrative command that provisions, inspects, and revokes the
narrow bearer-token credential field-acceptance tooling uses instead of an
operator's personal Administrator password. See docs/non-interactive-
field-acceptance-authentication-session-access-v1-contract.md for the full
design; this script is the one supported way to create/revoke that
credential.

## What this does and does not do

This never creates or elevates a human account. It signs in as an
*already-existing* local Administrator (exactly the way the product's own
sign-in screen would -- `POST /api/auth/sign-in`), then calls the new
Administrator-only `/api/admin/field-acceptance-credentials` endpoints this
same milestone adds. It cannot bootstrap the first Administrator itself
(use the product's own onboarding wizard, or `POST /api/setup/administrator`
directly, for that) -- provisioning a field-acceptance credential always
requires an already-authorized local administrative action, by design (see
the governing contract's "Provisioning contract": "Normal users must not
accidentally create this credential").

## Talking to the product

Like `scripts/repair_review_label_provenance.py`, this talks to a *running*
MockingBird instance over its real HTTP API rather than opening the SQLite
file directly, so it never races the live server's own connection/
transaction handling and reuses exactly the same validated repository
logic (password verification, role checks, audit logging) a real signed-in
Administrator's browser session would. Point `--base-url` at any reachable
instance.

## Credential handling

The Administrator password used to sign in in order to provision or revoke
a credential is **never** accepted as a command-line argument (which would
leak into shell history and process listings) -- only via an interactive,
unechoed prompt (`getpass`) or the `MOCKINGBIRD_ADMIN_PASSWORD` environment
variable for non-interactive/scripted use. Neither this script nor the
product itself ever prints it. The field-acceptance bearer token this
script's `create` subcommand mints is shown exactly once, to stdout only --
capture it immediately (for example into `MOCKINGBIRD_ACCEPTANCE_TOKEN` in
your own shell, or a local secret file with restrictive permissions); it
cannot be recovered afterward. `list` and `revoke` never print a secret.

## Usage

    # Provision a new 24-hour credential (the default TTL):
    python scripts/manage_field_acceptance_credential.py create

    # A longer- or shorter-lived credential, and/or a custom label:
    python scripts/manage_field_acceptance_credential.py create \\
        --ttl-hours 4 --label "Field Acceptance Operator (2026-09 cohort)"

    # See what credentials currently exist (no secrets shown):
    python scripts/manage_field_acceptance_credential.py list

    # Revoke one immediately -- it fails on its very next use:
    python scripts/manage_field_acceptance_credential.py revoke --credential-id field-acceptance-...

Every subcommand prompts for `--login-identity` (or reads
`MOCKINGBIRD_ADMIN_LOGIN_IDENTITY`) and a password (prompted via `getpass`,
or `MOCKINGBIRD_ADMIN_PASSWORD`) unless `--base-url` points at an instance
where sign-in fails for an unrelated reason, in which case this script
fails clearly rather than silently doing nothing.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://127.0.0.1:8000"


class FieldAcceptanceCredentialCommandError(RuntimeError):
    """A bounded, clearly-reported failure reason for this command."""


def _http_request(
    base_url: str,
    method: str,
    path: str,
    *,
    session_cookie: str | None = None,
    json_body: dict | None = None,
) -> tuple[int, dict | list | None, str | None]:
    url = f"{base_url.rstrip('/')}{path}"
    data = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    if session_cookie:
        request.add_header("Cookie", session_cookie)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - local product instance only
            cookie = response.headers.get("Set-Cookie")
            body = response.read()
            parsed = json.loads(body) if body else None
            return response.status, parsed, cookie
    except urllib.error.HTTPError as error:
        body = error.read()
        try:
            parsed = json.loads(body) if body else None
        except json.JSONDecodeError:
            parsed = None
        return error.code, parsed, None
    except urllib.error.URLError as error:
        raise FieldAcceptanceCredentialCommandError(
            f"Could not reach {base_url} -- is the product running there? ({error.reason})"
        ) from error


def _sign_in(base_url: str, args: argparse.Namespace) -> str:
    """Sign in as an existing local Administrator and return the resulting
    session cookie (`mb_session=...`). Never accepts a password via a CLI
    argument -- see the module docstring's "Credential handling"."""

    login_identity = args.login_identity or os.environ.get("MOCKINGBIRD_ADMIN_LOGIN_IDENTITY")
    if not login_identity:
        login_identity = input("Administrator login identity: ").strip()
    password = os.environ.get("MOCKINGBIRD_ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Administrator password (not echoed): ")
    if not login_identity or not password:
        raise FieldAcceptanceCredentialCommandError(
            "An existing local Administrator's login identity and password are required to "
            "provision or manage a field-acceptance credential -- see the module docstring."
        )
    status, body, cookie = _http_request(
        base_url, "POST", "/api/auth/sign-in",
        json_body={"login_identity": login_identity, "password": password},
    )
    del password  # not retained beyond this call
    if status != 200 or not cookie:
        detail = body.get("detail") if isinstance(body, dict) else None
        raise FieldAcceptanceCredentialCommandError(
            f"Sign-in failed ({status}): {detail or 'incorrect login identity or password'}."
        )
    if isinstance(body, dict) and body.get("role") != "administrator":
        raise FieldAcceptanceCredentialCommandError(
            "That account is signed in, but is not an Administrator -- provisioning a "
            "field-acceptance credential requires existing local administrative authority."
        )
    # Only the cookie's own `name=value` pair is needed on later requests.
    return cookie.split(";", 1)[0]


def _require_ok(status: int, body, action: str) -> dict | list:
    if status not in (200, 201):
        detail = body.get("detail") if isinstance(body, dict) else None
        raise FieldAcceptanceCredentialCommandError(f"{action} failed ({status}): {detail or body}")
    return body


def cmd_create(args: argparse.Namespace) -> int:
    cookie = _sign_in(args.base_url, args)
    status, body, _ = _http_request(
        args.base_url, "POST", "/api/admin/field-acceptance-credentials",
        session_cookie=cookie,
        json_body={"label": args.label, "expires_in_hours": args.ttl_hours},
    )
    created = _require_ok(status, body, "Creating field-acceptance credential")
    assert isinstance(created, dict)
    print("Field-acceptance credential created. Capture the token now -- it will not be shown again.")
    print(f"  id:          {created['id']}")
    print(f"  label:       {created['label']}")
    print(f"  created_at:  {created['created_at']}")
    print(f"  expires_at:  {created['expires_at']}")
    print(f"  token:       {created['token']}")
    print()
    print("Set this for field-acceptance tooling, for example:")
    print(f"  export MOCKINGBIRD_ACCEPTANCE_TOKEN={created['token']}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    cookie = _sign_in(args.base_url, args)
    status, body, _ = _http_request(
        args.base_url, "GET", "/api/admin/field-acceptance-credentials", session_cookie=cookie,
    )
    credentials = _require_ok(status, body, "Listing field-acceptance credentials")
    assert isinstance(credentials, list)
    if not credentials:
        print("No field-acceptance credentials exist.")
        return 0
    for entry in credentials:
        state = "revoked" if entry.get("revoked_at") else "active"
        print(
            f"{entry['id']}  [{state}]  label={entry['label']!r}  "
            f"created_at={entry['created_at']}  expires_at={entry['expires_at']}  "
            f"last_used_at={entry.get('last_used_at')}"
        )
    return 0


def cmd_revoke(args: argparse.Namespace) -> int:
    cookie = _sign_in(args.base_url, args)
    status, body, _ = _http_request(
        args.base_url, "POST", f"/api/admin/field-acceptance-credentials/{args.credential_id}/revoke",
        session_cookie=cookie,
    )
    revoked = _require_ok(status, body, "Revoking field-acceptance credential")
    assert isinstance(revoked, dict)
    print(f"Revoked {revoked['id']} ({revoked['label']!r}) at {revoked['revoked_at']}.")
    print("It will fail on its very next authentication attempt.")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"default: {DEFAULT_BASE_URL}")
    parser.add_argument(
        "--login-identity", default=None,
        help="Administrator login identity (or set MOCKINGBIRD_ADMIN_LOGIN_IDENTITY; otherwise prompted)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="Provision a new field-acceptance credential")
    create_parser.add_argument("--label", default="Field Acceptance Operator")
    create_parser.add_argument("--ttl-hours", type=int, default=24, help="1-720 (30 days); default 24")
    create_parser.set_defaults(func=cmd_create)

    list_parser = subparsers.add_parser("list", help="List existing field-acceptance credentials")
    list_parser.set_defaults(func=cmd_list)

    revoke_parser = subparsers.add_parser("revoke", help="Revoke a field-acceptance credential immediately")
    revoke_parser.add_argument("--credential-id", required=True)
    revoke_parser.set_defaults(func=cmd_revoke)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except FieldAcceptanceCredentialCommandError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
