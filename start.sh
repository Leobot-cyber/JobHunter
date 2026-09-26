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

API_PID=""
if lsof -ti :8000 >/dev/null 2>&1; then
  echo "检测到 8000 端口已有后端服务（可能是 launchd 常驻服务），跳过后端启动"
else
  export PYTHONPATH="$ROOT/backend"
  uvicorn app.main:app --app-dir backend --reload --port 8000 &
  API_PID=$!
fi
(cd frontend && npm run dev) &
UI_PID=$!

cleanup() {
  [[ -n "$API_PID" ]] && kill "$API_PID" 2>/dev/null || true
  kill "$UI_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "API  http://127.0.0.1:8000"
echo "UI   http://127.0.0.1:5173"
wait
