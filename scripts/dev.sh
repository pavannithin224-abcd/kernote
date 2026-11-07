#!/usr/bin/env bash
# Fallback dev launcher for when `just` and `honcho` are unavailable.
set -euo pipefail
cd "$(dirname "$0")/.."
export PATH="$HOME/.local/bin:$PATH"
backend/.venv/bin/python -m uvicorn kernote.main:app --app-dir backend \
  --host 127.0.0.1 --port 8787 --reload &
API=$!
trap 'kill $API 2>/dev/null || true' EXIT
npm --prefix frontend run dev
