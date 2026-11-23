#!/usr/bin/env bash
# MEDELTOMTEN - engångsinstallation för macOS/Linux (kräver internet).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements-dev.txt
(cd frontend && npm ci && npm run build)
echo "Klart. Starta med: scripts/start.sh"
