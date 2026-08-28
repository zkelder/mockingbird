#!/usr/bin/env python3
"""Non-Interactive Field Acceptance Authentication & Session Access v1: a
small, focused HTTP client field-acceptance sessions use to reach the real
local product's Stream/Observation/Visit/counterfactual endpoints with the
bearer-token credential `scripts/manage_field_acceptance_credential.py`
provisions -- see docs/non-interactive-field-acceptance-authentication-
session-access-v1-contract.md for the full design.

## What this is (and is not)

This is the "acceptance tooling" the governing contract's "Tooling
integration" section asks to be updated to use the supported mechanism --
before this milestone, no dedicated wrapper for this HTTP sequence existed
at all (every prior field-acceptance report documented the exact manual
`curl`/REST sequence instead; see e.g. representative-daylight-field-
acceptance-gate-a-evidence-v2-report.md's own "Readiness for the next
viable session"). It is deliberately **not** a full field-session launcher
(no tmux orchestration, no acceptance-recorder wiring, no post-session
accounting) -- that broader gap was explicitly named and explicitly left
out of scope by that same prior report ("A dedicated single-command
field-session launcher does not exist ... Not fixed here (would be
tooling/feature work, out of this milestone's bounded scope)"), and stays
out of scope here too. This module only closes the specific, narrow gap
this milestone owns: authenticating the HTTP calls that gap's own next user
will still make by hand or from a short script of their own, using this
class instead of raw unauthenticated `requests.get(...)` calls.

## Credential source

Reads `MOCKINGBIRD_ACCEPTANCE_TOKEN` from the environment (never a CLI
argument, never a config file this module writes) and sends it as
`Authorization: Bearer <token>` on every request -- standard bearer-token
header behavior, no token ever placed in a URL or query string. Fails
clearly and immediately (`FieldAcceptanceCredentialMissingError`) if unset,
rather than silently making an unauthenticated request that would 401 deep
inside some later call.

## Usage

    from field_acceptance_client import FieldAcceptanceClient

    client = FieldAcceptanceClient()  # reads MOCKINGBIRD_ACCEPTANCE_TOKEN
    streams = client.list_streams()
    client.start_observation(stream_id)
    ...
    client.stop_observation(stream_id)

Or, as a bounded read-only smoke test proving the credential actually
authenticates against a real running instance (used during this
milestone's own real-acceptance proof; see the governing report):

    python scripts/field_acceptance_client.py --base-url http://127.0.0.1:8000 smoke-test

    # Additionally exercises a real bounded Observation start -> stop cycle
    # on one named Stream (has real recording/resource consequences -- only
    # pass this for a Stream you intend to actually smoke-test):
    python scripts/field_acceptance_client.py smoke-test --stream-id <id>
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
ACCEPTANCE_TOKEN_ENV_VAR = "MOCKINGBIRD_ACCEPTANCE_TOKEN"


class FieldAcceptanceClientError(RuntimeError):
    """Base class for every error this client raises -- always a clear,
    specific reason (see the subclasses below), never a bare traceback from
    inside `urllib`."""


class FieldAcceptanceCredentialMissingError(FieldAcceptanceClientError):
    """`MOCKINGBIRD_ACCEPTANCE_TOKEN` is unset. No anonymous fallback exists
    -- see the governing contract's "Tooling integration"."""


class FieldAcceptanceCredentialInvalidError(FieldAcceptanceClientError):
    """The server returned 401. Deliberately indistinguishable, at this
    layer, between an unknown/malformed token, an expired one, and a
    revoked one -- `resolve_field_acceptance_token` (like `resolve_session`
    before it) returns the same generic outcome for all three so a caller
    cannot use response shape as an oracle for which is true. Re-provision
    a fresh credential via `scripts/manage_field_acceptance_credential.py
    create`."""


class FieldAcceptancePermissionError(FieldAcceptanceClientError):
    """The server returned 403: the credential authenticated, but this
    action is outside its narrow allowed scope (see the governing
    contract's "Principle of least privilege"). This is expected and
    correct for anything beyond the specific field-acceptance workflow --
    it is not a bug in this client."""


class FieldAcceptanceApiError(FieldAcceptanceClientError):
    """Any other non-2xx response (404, 400, ...) -- a real API-level
    error unrelated to authentication/authorization."""

    def __init__(self, status: int, detail: str | None) -> None:
        super().__init__(f"HTTP {status}: {detail or '(no detail)'}")
        self.status = status
        self.detail = detail


class FieldAcceptanceClient:
    """Thin authenticated HTTP wrapper. Stdlib-only (`urllib`), matching
    `scripts/repair_review_label_provenance.py`'s own precedent -- no new
    dependency for a bounded acceptance-tooling script."""

    def __init__(self, *, base_url: str = DEFAULT_BASE_URL, token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self._token = token if token is not None else os.environ.get(ACCEPTANCE_TOKEN_ENV_VAR)
        if not self._token:
            raise FieldAcceptanceCredentialMissingError(
                f"No field-acceptance credential configured -- set {ACCEPTANCE_TOKEN_ENV_VAR} "
                "(see scripts/manage_field_acceptance_credential.py create)."
            )

    def _request(self, method: str, path: str, *, params: dict | None = None) -> dict | list:
        url = f"{self.base_url}{path}"
        if params:
            query = "&".join(f"{key}={value}" for key, value in params.items() if value is not None)
            if query:
                url = f"{url}?{query}"
        request = urllib.request.Request(url, method=method)
        request.add_header("Authorization", f"Bearer {self._token}")
        try:
            with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - local product instance only
                body = response.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as error:
            body = error.read()
            try:
                detail = json.loads(body).get("detail") if body else None
            except (json.JSONDecodeError, AttributeError):
                detail = None
            if error.code == 401:
                raise FieldAcceptanceCredentialInvalidError(
                    detail or "Field-acceptance credential is missing, invalid, expired, or revoked."
                ) from error
            if error.code == 403:
                raise FieldAcceptancePermissionError(
                    detail or "Field-acceptance credential lacks permission for this action."
                ) from error
            raise FieldAcceptanceApiError(error.code, detail) from error
        except urllib.error.URLError as error:
            raise FieldAcceptanceClientError(
                f"Could not reach {self.base_url} -- is the product running there? ({error.reason})"
            ) from error

    # --- The exact workflow named in the governing brief's §4/§19 --------

    def list_streams(self) -> list:
        return self._request("GET", "/api/streams")

    def list_visits(self, **query_params) -> list:
        return self._request("GET", "/api/visits", params=query_params)

    def start_observation(self, stream_id: str) -> dict:
        return self._request("POST", f"/api/streams/{stream_id}/observation/start")

    def stop_observation(self, stream_id: str) -> dict:
        return self._request("POST", f"/api/streams/{stream_id}/observation/stop")

    def observation_status(self, stream_id: str) -> dict:
        return self._request("GET", f"/api/streams/{stream_id}/observation/status")

    def observation_counterfactual(
        self, stream_id: str, *, start_offset_ms: int, end_offset_ms: int
    ) -> dict:
        return self._request(
            "GET", f"/api/streams/{stream_id}/observation/counterfactual",
            params={"start_offset_ms": start_offset_ms, "end_offset_ms": end_offset_ms},
        )

    def product_health(self) -> dict:
        """Public, unauthenticated (`/api/product/health`) -- included for
        convenience so one client covers the whole readiness sequence, not
        because this call needs the bearer token."""

        return self._request("GET", "/api/product/health")


def _smoke_test(args: argparse.Namespace) -> int:
    client = FieldAcceptanceClient(base_url=args.base_url)
    health = client.product_health()
    print(f"product/health: ready={health.get('ready')}, schema={health.get('database_schema_version')}")
    streams = client.list_streams()
    print(f"GET /api/streams: {len(streams)} Stream(s) -- authenticated read succeeded.")
    visits = client.list_visits(limit=1)
    print(f"GET /api/visits: authenticated read succeeded ({len(visits)} row(s) returned).")
    if args.stream_id:
        print(f"Starting Observation on Stream {args.stream_id} ...")
        client.start_observation(args.stream_id)
        time.sleep(args.observation_seconds)
        status = client.observation_status(args.stream_id)
        print(f"Observation status mid-run: {status.get('lane', status)}")
        client.stop_observation(args.stream_id)
        print("Stopped Observation.")
    print("Smoke test passed: the field-acceptance credential authenticated every required call.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    subparsers = parser.add_subparsers(dest="command", required=True)

    smoke_parser = subparsers.add_parser(
        "smoke-test", help="Prove the configured credential authenticates against a real instance"
    )
    smoke_parser.add_argument(
        "--stream-id", default=None,
        help="If given, also runs a bounded real Observation start -> stop cycle on this Stream.",
    )
    smoke_parser.add_argument("--observation-seconds", type=int, default=5)

    args = parser.parse_args(argv)
    try:
        if args.command == "smoke-test":
            return _smoke_test(args)
        parser.error(f"unknown command {args.command!r}")
        return 2
    except FieldAcceptanceClientError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
