#!/usr/bin/env bash
# 安装 JobHunter 后端为 macOS 常驻服务（launchd LaunchAgent）。
# 特性：开机自启、崩溃自动重启（KeepAlive）、日志落盘。
#
# 用法：
#   bash scripts/install_backend_service.sh              # 安装并启动
#   bash scripts/install_backend_service.sh --uninstall  # 卸载
#   bash scripts/install_backend_service.sh --status     # 查看状态
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LABEL="com.jobhunter.backend"
PLIST_DST="$HOME/Library/LaunchAgents/${LABEL}.plist"
VENV_UVICORN="$ROOT/.venv/bin/uvicorn"
GUI_TARGET="gui/$(id -u)"

if [[ "${1:-}" == "--uninstall" ]]; then
  launchctl bootout "$GUI_TARGET" "$PLIST_DST" 2>/dev/null || launchctl remove "$LABEL" 2>/dev/null || true
  rm -f "$PLIST_DST"
  echo "✅ 已卸载 $LABEL"
  exit 0
fi

if [[ "${1:-}" == "--status" ]]; then
  launchctl print "$GUI_TARGET/$LABEL" 2>/dev/null | grep -E "state|pid" || echo "服务未安装或未运行"
  exit 0
fi

[[ -x "$VENV_UVICORN" ]] || { echo "❌ 未找到 $VENV_UVICORN，请先运行 ./setup.sh"; exit 1; }

# 若 8000 端口已有后端在跑，先停掉，避免端口冲突
if lsof -ti :8000 >/dev/null 2>&1; then
  echo "停止占用 8000 端口的进程: $(lsof -ti :8000 | tr '\n' ' ')"
  lsof -ti :8000 | xargs kill 2>/dev/null || true
  sleep 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST_DST" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array>
    <string>$VENV_UVICORN</string>
    <string>app.main:app</string>
    <string>--host</string>
    <string>127.0.0.1</string>
    <string>--port</string>
    <string>8000</string>
  </array>
  <key>WorkingDirectory</key><string>$ROOT/backend</string>
  <key>EnvironmentVariables</key>
  <dict>
    <key>PYTHONPATH</key><string>$ROOT/backend</string>
    <key>PATH</key><string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
  </dict>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardOutPath</key><string>$ROOT/backend/backend.log</string>
  <key>StandardErrorPath</key><string>$ROOT/backend/backend.err.log</string>
</dict>
</plist>
EOF

# 幂等：先卸载旧实例再装载
launchctl bootout "$GUI_TARGET" "$PLIST_DST" 2>/dev/null || true
launchctl bootstrap "$GUI_TARGET" "$PLIST_DST"

echo "✅ 已安装并启动常驻服务 $LABEL"
echo "   验证: curl http://127.0.0.1:8000/api/health"
echo "   日志: backend/backend.log / backend/backend.err.log"
echo "   卸载: bash scripts/install_backend_service.sh --uninstall"
