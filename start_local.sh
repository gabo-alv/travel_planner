#!/usr/bin/.env bash
set -euo pipefail

cd "$(dirname "$0")/python-worker"

# Force Python version
PYTHON_BIN="python3.11"

# Create venv with correct interpreter
if [ ! -d ".venv" ]; then
  echo "[worker] Creating virtualenv..."
  $PYTHON_BIN -m venv .venv
fi

# Use ABSOLUTE interpreter INSIDE the venv
VENV_PY="./.venv/bin/python"

echo "[worker] Using interpreter: $($VENV_PY -c 'import sys; print(sys.executable)')"

# Install deps if missing
if ! $VENV_PY -c "import temporalio" >/dev/null 2>&1; then
  echo "[worker] Installing dependencies..."
  $VENV_PY -m pip install --upgrade pip
  $VENV_PY -m pip install -r requirements.txt
fi

echo "[worker] Starting Temporal worker..."
exec $VENV_PY temporal_worker.py
