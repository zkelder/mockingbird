"""The Node's outbound transport credential -- deliberately separate from pairing.

`app.py`'s `_PairingState` stores only a SHA-256 digest of the pairing
credential because the Node only ever *verifies* it (the host presents it).
Node -> host transport calls need the inverse: the Node must *present* a
credential, including after an unattended restart with nobody back on site
(Phase I is unconditional on this) -- which a digest alone cannot do.

Rather than weaken `_PairingState`'s existing "never stores its bearer"
property, this is one new, narrowly-scoped, plaintext-at-rest secret:
minted once by the Node, returned to the host as an additive field on the
existing `/node/v1/pair` response, and persisted 0o600 in the same hardened
`StateDirectory=` the pairing digest already relies on (see
docs/remote-intermittent-wan-transport-v1-design.md, "Authentication for
the new direction" -- this trade-off is deliberate and documented, not an
oversight).
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import secrets

from .atomic_io import atomic_write_bytes

_STATE_VERSION = 1


@dataclass(frozen=True)
class TransportCredentialState:
    credential: str
    node_id: str


def load_transport_credential(state_path: Path, *, expected_node_id: str) -> str | None:
    """Return the persisted credential, or None if absent/invalid/stale.

    A credential minted for a *different* `node_id` (the Node's identity is
    derived from `display_name` -- see `app.py`) is treated the same as
    "none" rather than presented under the wrong identity: a rename is rare
    but should fail safe (re-pair) rather than silently misrepresent
    identity to the host.
    """

    try:
        raw = state_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        return None
    try:
        payload = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(payload, dict) or payload.get("version") != _STATE_VERSION:
        return None
    credential, node_id = payload.get("credential"), payload.get("node_id")
    if not isinstance(credential, str) or not credential or not isinstance(node_id, str):
        return None
    if node_id != expected_node_id:
        return None
    return credential


def mint_and_persist_transport_credential(state_path: Path, *, node_id: str) -> str:
    """Generate a fresh credential and durably persist it before returning it.

    Persistence happens *before* the caller can hand the credential to a
    client (the pairing response) -- if the write fails, pairing itself
    fails loudly rather than handing out a credential the Node cannot later
    present again after a restart.
    """

    credential = secrets.token_urlsafe(32)
    payload = json.dumps(
        {"version": _STATE_VERSION, "credential": credential, "node_id": node_id},
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    atomic_write_bytes(state_path, payload, mode=0o600)
    return credential


def clear_transport_credential(state_path: Path) -> None:
    """Best-effort removal, e.g. on pairing revoke. Never raises."""

    try:
        state_path.unlink()
    except OSError:
        pass
