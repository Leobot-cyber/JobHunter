#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r backend/requirements.txt

if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && npm install)
fi

export PYTHONPATH="$ROOT/backend"
uvicorn app.main:app --app-dir backend --reload --port 8000 &
API_PID=$!
(cd frontend && npm run dev) &
UI_PID=$!

cleanup() {
  kill "$API_PID" "$UI_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "API  http://127.0.0.1:8000"
echo "UI   http://127.0.0.1:5173"
wait
