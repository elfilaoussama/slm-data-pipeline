#!/usr/bin/env bash
set -euo pipefail

# Re-run the pilot deterministically using a local venv
# Usage:
#   ./reproduce.sh                 # create .venv if missing, install deps, run pipeline
#   ./reproduce.sh --install-only  # only set up venv and install deps
#   RUN_PIPELINE=0 ./reproduce.sh  # env-based way to skip running pipeline

RUN_PIPELINE=${RUN_PIPELINE:-1}
if [[ "${1:-}" == "--install-only" ]]; then
	RUN_PIPELINE=0
fi

# choose python executable
PYTHON_BIN="python3"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
	PYTHON_BIN="python"
fi

VENV_DIR=".venv"
if [[ ! -d "$VENV_DIR" ]]; then
	echo "[setup] Creating virtual environment in $VENV_DIR"
	"$PYTHON_BIN" -m venv "$VENV_DIR"
fi

echo "[setup] Activating virtual environment"
source "$VENV_DIR/bin/activate"

echo "[deps] Upgrading pip and installing requirements"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [[ "$RUN_PIPELINE" == "1" ]]; then
	echo "[run] Starting pipeline"
	python pipeline.py
else
	echo "[run] Skipped. Venv is ready with dependencies installed."
fi
