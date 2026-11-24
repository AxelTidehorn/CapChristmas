#!/usr/bin/env bash
# MEDELTOMTEN - engångsinstallation för macOS/Linux (kräver internet).
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r backend/requirements.txt
if [ -f frontend/dist/index.html ]; then
  echo "Färdigbyggt gränssnitt finns. Node.js behövs inte."
else
  command -v npm >/dev/null || { echo "Hämta det färdigbyggda paketet för installation utan Node.js."; exit 1; }
  (cd frontend && npm ci && npm run build)
fi
echo "Klart. Starta med: scripts/start.sh"
