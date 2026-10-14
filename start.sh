#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
if [ ! -x "$ROOT/backend/.venv/bin/python" ] || [ ! -d "$ROOT/frontend/node_modules" ]; then
  echo "Install dependencies using README.md first."
  exit 1
fi
(cd "$ROOT/backend" && .venv/bin/python -m app.seed)
(cd "$ROOT/backend" && exec .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000) &
BACKEND_PID=$!
(cd "$ROOT/frontend" && exec npm run dev) &
FRONTEND_PID=$!
trap 'kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true' EXIT INT TERM
printf 'UniSync: http://127.0.0.1:5173\nPress Ctrl+C to stop.\n'
wait
