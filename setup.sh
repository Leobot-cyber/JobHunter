#!/bin/bash
set -e

# ── JobHunter 一键安装脚本 ──
# 自动安装 Ollama + 拉取模型 + 安装依赖 + 启动服务 + 打开浏览器

echo " JobHunter 一键安装"
echo "===================="

# ── 1. 检测系统 ──
OS="$(uname -s)"
ARCH="$(uname -m)"
echo "📱 系统: $OS ($ARCH)"

# ── 2. 安装 Ollama（如果未安装）──
if ! command -v ollama &> /dev/null; then
    echo "📦 安装 Ollama..."
    if [ "$OS" = "Darwin" ]; then
        if ! command -v brew &> /dev/null; then
            echo "❌ 需要先安装 Homebrew: https://brew.sh"
            exit 1
        fi
        brew install ollama
    elif [ "$OS" = "Linux" ]; then
        curl -fsSL https://ollama.com/install.sh | sh
    else
        echo "❌ 不支持的系统: $OS"
        echo "请手动安装 Ollama: https://ollama.com/download"
        exit 1
    fi
else
    echo "✅ Ollama 已安装"
fi

# ── 3. 启动 Ollama 服务 ──
echo "🔧 启动 Ollama 服务..."
if ! pgrep -x "ollama" > /dev/null; then
    if [ "$OS" = "Darwin" ]; then
        # macOS: 使用 launchd 或后台运行
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        echo "⏳ 等待 Ollama 服务启动..."
        sleep 3
    else
        nohup ollama serve > /tmp/ollama.log 2>&1 &
        sleep 3
    fi
else
    echo "✅ Ollama 服务已在运行"
fi

# ── 4. 选择并拉取模型 ──
echo ""
echo "🤖 选择要使用的本地模型:"
echo "  1) qwen2.5:7b      (推荐，4.7GB，中文优秀)"
echo "  2) qwen2.5:14b     (更强，9GB)"
echo "  3) llama3.2:3b     (轻量，2GB)"
echo "  4) llama3.1:8b     (均衡，4.7GB)"
echo "  5) mistral:7b      (英文优秀，4.1GB)"
echo ""
read -p "请输入选项 [1-5] (默认 1): " MODEL_CHOICE
MODEL_CHOICE=${MODEL_CHOICE:-1}

case $MODEL_CHOICE in
    1) MODEL="qwen2.5:7b" ;;
    2) MODEL="qwen2.5:14b" ;;
    3) MODEL="llama3.2:3b" ;;
    4) MODEL="llama3.1:8b" ;;
    5) MODEL="mistral:7b" ;;
    *) MODEL="qwen2.5:7b" ;;
esac

echo "📥 拉取模型: $MODEL"
if ollama list | grep -q "$MODEL"; then
    echo "✅ 模型已存在"
else
    ollama pull "$MODEL"
fi

# ── 5. 安装后端依赖 ──
echo ""
echo "🐍 安装后端依赖..."
cd "$(dirname "$0")"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r backend/requirements.txt

# ── 6. 安装前端依赖 ──
echo "📦 安装前端依赖..."
cd frontend
npm install --silent
cd ..

# ── 7. 配置环境变量 ──
echo "⚙️  配置环境变量..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "✅ 已创建 .env 文件"
else
    echo "✅ .env 已存在"
fi

# ── 8. 启动服务 ──
echo ""
echo "🚀 启动服务..."

# 启动后端
echo "📡 启动后端 API (http://localhost:8000)..."
source .venv/bin/activate
cd backend
nohup uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 > /tmp/jobhunter-backend.log 2>&1 &
BACKEND_PID=$!
cd ..

# 启动前端
echo " 启动前端 UI (http://localhost:5173)..."
cd frontend
nohup npm run dev > /tmp/jobhunter-frontend.log 2>&1 &
FRONTEND_PID=$!
cd ..

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 5

# ── 9. 打开浏览器 ──
echo ""
echo "✅ 安装完成！"
echo "📡 后端 API: http://localhost:8000"
echo "🎨 前端 UI:  http://localhost:5173"
echo ""
echo " 打开浏览器..."

if [ "$OS" = "Darwin" ]; then
    open http://localhost:5173
elif [ "$OS" = "Linux" ]; then
    if command -v xdg-open &> /dev/null; then
        xdg-open http://localhost:5173
    else
        echo "请手动打开: http://localhost:5173"
    fi
fi

echo ""
echo " 服务信息:"
echo "  后端 PID: $BACKEND_PID"
echo "  前端 PID: $FRONTEND_PID"
echo "  模型: $MODEL"
echo ""
echo "🛑 停止服务:"
echo "  kill $BACKEND_PID $FRONTEND_PID"
echo ""
echo "📖 查看日志:"
echo "  后端: tail -f /tmp/jobhunter-backend.log"
echo "  前端: tail -f /tmp/jobhunter-frontend.log"
echo "  Ollama: tail -f /tmp/ollama.log"
echo ""
echo "🎉 开始使用 JobHunter！"
