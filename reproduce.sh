#!/usr/bin/env bash
set -euo pipefail

# Re-run the pilot deterministically.
python -m pip install -r requirements.txt
python pipeline.py
