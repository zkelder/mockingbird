#!/usr/bin/env bash
# Linux/macOS equivalent of "Start MockingBird.cmd": the normal double-click
# (or `./start-mockingbird.sh`) entry point for a MockingBird *development
# checkout*. It never asks the user to type a Python/uvicorn/npm command --
# it finds the local virtual environment itself and launches the same
# unified `python -m mockingbird` product runtime the Windows launcher does.
#
# This is separate from scripts/build_local_product.py, which produces the
# distributable Windows bundle for a user with no checkout, no Python, and
# no venv at all. This script still expects a checkout with `.venv`/
# `.venv312` already created per README.md's developer setup.
set -euo pipefail

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$ROOT_DIR"

if [ -x ".venv312/bin/python" ]; then
  PYTHON_BIN=".venv312/bin/python"
elif [ -x ".venv/bin/python" ]; then
  PYTHON_BIN=".venv/bin/python"
else
  PYTHON_BIN="python3"
fi

exec "$PYTHON_BIN" -m mockingbird "$@"
