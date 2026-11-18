#!/usr/bin/env bash
# Run Kernote as a single process: build the UI, then serve it and the API
# from one uvicorn on one port. The `just`-free equivalent of `just app`.
#
# Development still wants two processes (scripts/dev.sh) for hot reload.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"

if [ ! -f frontend/dist/index.html ] || [ "${KERNOTE_REBUILD:-1}" = "1" ]; then
  echo "building the UI…"
  npm --prefix frontend run build
fi

# One origin, so the dev CORS allowance is pure attack surface here.
export KERNOTE_CORS_ORIGINS='[]'

echo "Kernote on http://127.0.0.1:8787"
exec backend/.venv/bin/python -m uvicorn kernote.main:app \
  --app-dir backend --host 127.0.0.1 --port 8787
