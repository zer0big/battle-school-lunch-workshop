#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_DIR="$BACKEND_DIR/.venv"

if [[ -x "$VENV_DIR/bin/python" ]]; then
  PYTHON_BIN="$VENV_DIR/bin/python"
else
  PYTHON_BIN="$VENV_DIR/Scripts/python.exe"
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  python -m venv "$VENV_DIR"
  if [[ -x "$VENV_DIR/bin/python" ]]; then
    PYTHON_BIN="$VENV_DIR/bin/python"
  else
    PYTHON_BIN="$VENV_DIR/Scripts/python.exe"
  fi
fi

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install -r "$BACKEND_DIR/requirements.txt"
cd "$BACKEND_DIR"
"$PYTHON_BIN" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
