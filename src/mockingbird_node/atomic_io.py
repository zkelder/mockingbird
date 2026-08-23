"""Shared atomic-write helper for Camera Node local durable state.

Factored out of the exact pattern `app.py`'s `_PairingState._persist_state`
already used (create-in-temp with `O_CREAT|O_EXCL`, `flush`+`fsync`,
`os.replace`) so the Remote / Intermittent-WAN Transport Foundation v1
spool and transport-credential store reuse one correct implementation
instead of a second hand-rolled copy of the same tricky code.
"""

from __future__ import annotations

import os
from pathlib import Path
import secrets


def atomic_write_bytes(path: Path, payload: bytes, *, mode: int = 0o600) -> None:
    """Write `payload` to `path` durably: readers never observe a partial file.

    On any interruption before the final `os.replace`, `path` itself is left
    completely untouched (either the old content, if any, or absent) -- the
    only artifact of a failed write is an orphaned `.tmp` file, which callers
    that scan this directory should treat as safe to ignore/clean up.
    """

    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{secrets.token_hex(8)}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, mode)
    finally:
        if temporary.exists():
            temporary.unlink()
