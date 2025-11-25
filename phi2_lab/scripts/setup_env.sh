#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd -- "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-${PROJECT_ROOT}/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "[setup_env] Python interpreter not found: ${PYTHON_BIN}" >&2
  exit 1
fi

echo "[setup_env] Creating virtual environment at ${VENV_DIR}" 
"$PYTHON_BIN" -m venv "$VENV_DIR"

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install --upgrade wheel setuptools

# Install the package in editable mode to expose scripts and dependencies.
echo "[setup_env] Installing phi2-lab in editable mode"
pip install -e "$PROJECT_ROOT"

cat <<EOM

[setup_env] Environment ready.
To activate: source "$VENV_DIR/bin/activate"
To run the smoke test: python "$PROJECT_ROOT/scripts/self_check.py"
EOM
