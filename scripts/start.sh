#!/usr/bin/env bash
# MEDELTOMTEN - start (offline efter install.sh).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -x .venv/bin/python ] || { echo "Kör scripts/install.sh först."; exit 1; }
[ -f frontend/dist/index.html ] || { echo "Frontend ej byggd - kör scripts/install.sh."; exit 1; }
PORT="${MEDELTOMTEN_PORT:-8000}"
echo "MEDELTOMTEN kör på http://127.0.0.1:$PORT/control"
cd backend && exec ../.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
