# JobHunter - AI 求职助手

基于 LangGraph 编排的智能求职 Agent，支持多模型接入和公开招聘源筛选。

## ✨ 特性

- 🤖 **智能对话** - 基于 LangGraph + ReAct Agent 的自然语言交互
- 🔍 **多源聚合** - 同时搜索 Remotive、RemoteOK、Arbeitnow、The Muse 等公开岗位
- 🧠 **多模型支持** - 支持 Ollama 本地模型、OpenAI、Anthropic、DeepSeek 等
- 🎨 **苹果风格 UI** - 简洁现代的界面设计
- 📱 **响应式布局** - 适配桌面和移动端
- 🔧 **可观测编排** - 实时显示 Agent 工作流程（phase/parallel/pipeline）

## 🚀 快速开始

### 一键安装（推荐）

```bash
# 克隆仓库
git clone https://github.com/Leobot-cyber/JobHunter.git
cd JobHunter

# 运行安装脚本（自动安装 Ollama + 拉取模型 + 安装依赖 + 启动服务）
chmod +x setup.sh
./setup.sh
```

安装脚本会自动：
1. 检测并安装 Ollama（如未安装）
2. 让你选择要使用的本地模型
3. 安装 Python 和 Node.js 依赖
4. 启动后端和前端服务
5. 自动打开浏览器访问 http://localhost:5173

### 手动安装

#### 1. 安装 Ollama（本地模型推理）

**macOS:**
```bash
brew install ollama
ollama serve  # 启动服务
```

**Linux:**
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

#### 2. 拉取模型

```bash
# 推荐模型（中文优秀，4.7GB）
ollama pull qwen2.5:7b

# 其他可选模型
ollama pull qwen2.5:14b   # 更强，9GB
ollama pull llama3.2:3b   # 轻量，2GB
ollama pull llama3.1:8b   # 均衡，4.7GB
```

#### 3. 安装后端依赖

```bash
cd JobHunter
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

#### 4. 安装前端依赖

```bash
cd frontend
npm install
```

#### 5. 启动服务

**终端 1 - 后端:**
```bash
cd backend
source ../.venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**终端 2 - 前端:**
```bash
cd frontend
npm run dev
```

访问 http://localhost:5173

## 📖 使用指南

### 1. 配置模型

首次使用需要配置模型：

1. 点击左下角 **⚙️ 模型设置**
2. 选择 Provider：
   - **ollama** - 本地模型（推荐，无需 API Key）
   - **openai_compat** - DeepSeek/Qwen 等兼容 OpenAI 的 API
   - **openai** - OpenAI 官方 API
   - **anthropic** - Claude API
3. 如使用 Ollama，可在设置页面直接安装/切换模型
4. 点击 **保存**

### 2. 开始对话

在输入框描述你想找的工作方向，例如：

- "远程 Python 后端，关键词 FastAPI, LangGraph"
- "前端 React 工程师，旧金山湾区"
- "数据科学，远程，Python"

Agent 会自动：
1. 理解你的需求
2. 调用搜索工具从多个招聘源获取岗位
3. 筛选并排序最匹配的岗位
4. 返回结果并展示在界面中

### 3. 管理对话

- **新建对话** - 点击左侧边栏顶部的 **+** 按钮
- **切换对话** - 点击左侧边栏中的对话标题
- **删除对话** - hover 对话项，点击出现的 **×**

### 4. 岗位管理

- **查看岗位** - 对话中会实时显示匹配的岗位卡片
- **收藏岗位** - 点击岗位卡片右上角的 **☆** 星标
- **筛选岗位** - 使用顶部的关键词和地点筛选器

## 🏗️ 架构说明

### 技术栈

**后端:**
- FastAPI - Web 框架
- LangGraph - Agent 编排
- LangChain - LLM 集成
- SSE - 实时事件流

**前端:**
- React 18 + TypeScript
- Vite - 构建工具
- 原生 CSS（苹果风格设计系统）

**模型:**
- Ollama - 本地模型推理
- OpenAI / Anthropic / DeepSeek - 云端 API

### 核心模块

```
backend/app/
├── agent/          # Agent 编排
│   ├── supervisor.py    # ReAct Agent 主循环
│   ├── tools.py         # 工具定义（搜索、收藏等）
│   ├── events.py        # SSE 事件总线
│   ├── hunt_graph.py    # LangGraph 确定性流水线
│   └── workflow_engine.py  # DeepSeek harness 风格编排
├── jobs/           # 招聘源适配器
│   ├── adapters/        # Remotive, RemoteOK, Arbeitnow, The Muse
│   └── registry.py      # 并行检索 + 去重
├── llm.py          # 多模型工厂
├── settings.py     # 配置管理
└── main.py         # API 入口
```

### Agent 工作流程

```
用户输入
  ↓
[LangGraph Supervisor]
  ↓ 理解意图，选择工具
  ↓
[工具调用]
  ├─ search_public_jobs  → 并行请求 4 个招聘 API
  ├─ run_hunt_pipeline   → 完整流水线（plan→search→rank→report）
  ─ run_workflow        → harness 风格编排
  ↓
[模型生成回复]
  ↓
[SSE 流式返回]
  ↓
前端实时显示
```

## 🔧 开发

### 后端开发

```bash
cd backend
source ../.venv/bin/activate
uvicorn app.main:app --reload
```

API 文档: http://localhost:8000/docs

### 前端开发

```bash
cd frontend
npm run dev
```

热更新已配置，修改代码后自动刷新。

### 添加新的招聘源

1. 在 `backend/app/jobs/adapters/` 创建新适配器
2. 实现 `JobAdapter` 协议
3. 在 `registry.py` 中注册

示例:
```python
from app.jobs.base import JobAdapter, Job

class MyAdapter(JobAdapter):
    id = "my_source"
    label = "My Job Board"
    
    async def search(self, keywords: str, location: str = "") -> list[Job]:
        # 实现搜索逻辑
        pass
```

## 📝 环境变量

复制 `.env.example` 为 `.env` 并配置：

```env
# 模型配置（可选，也可在网页中配置）
LLM_PROVIDER=ollama
LLM_BASE_URL=http://127.0.0.1:11434/v1
LLM_MODEL=qwen2.5:7b
LLM_API_KEY=
LLM_TEMPERATURE=0.2

# 招聘源（逗号分隔）
JOB_SOURCES=remotive,remoteok,arbeitnow,themuse
```

## 🐛 故障排除

### Ollama 服务未启动

```bash
# 检查服务状态
ollama list

# 手动启动
ollama serve
```

### 前端无法连接后端

确保后端运行在 `http://localhost:8000`，前端运行在 `http://localhost:5173`。

### 模型响应慢

- 使用更小的模型（如 `llama3.2:3b`）
- 检查 GPU 是否被其他程序占用
- M4 芯片通常能达到 30-50 tokens/秒

### SSE 连接失败

检查浏览器控制台是否有 CORS 错误。确保后端 CORS 配置包含前端地址。

## 📄 许可证

MIT License

## 🙏 致谢

- [LangGraph](https://github.com/langchain-ai/langgraph) - Agent 编排框架
- [Ollama](https://ollama.com/) - 本地模型推理
- [FastAPI](https://fastapi.tiangolo.com/) - Web 框架
- [Vite](https://vitejs.dev/) - 前端构建工具

---

**作者**: Leobot-cyber  
**项目地址**: https://github.com/Leobot-cyber/JobHunter
