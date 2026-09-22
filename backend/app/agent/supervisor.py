from __future__ import annotations

from typing import Any

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from app.agent.events import bus
from app.agent.tools import TOOLS, thread_id_var
from app.llm import build_chat_model
from app.settings import load_settings

SYSTEM = """你是 JobHunter，一个求职研究 Agent。

工作方式（学习项目，刻意暴露编排）：
1. 用户要找工作时，优先调用 run_workflow（DeepSeek harness 风格：phase / parallel / pipeline / agent / log）。
2. 用户只要快速列表时，调用 search_public_jobs。
3. 用户要完整流水线讲解或更稳的确定性路径时，调用 run_hunt_pipeline（LangGraph：plan → search → rank → report）。
4. 需要收藏时调用 save_job；需要看详情调用 get_job_detail。

数据源是公开 API：Remotive、RemoteOK、Arbeitnow、The Muse。
不要声称能登录 Boss 直聘 / 拉勾 / LinkedIn；可以建议用户把关键词映射到这些公开源。
回复用中文，简洁，列出最匹配的岗位并附上来源链接。
"""

_checkpointer = MemorySaver()
_graph = None
_graph_fingerprint = ""


def _fingerprint() -> str:
    s = load_settings()
    return f"{s.provider}|{s.base_url}|{s.model}|{s.temperature}|{bool(s.api_key)}"


def get_graph():
    global _graph, _graph_fingerprint
    fp = _fingerprint()
    if _graph is not None and fp == _graph_fingerprint:
        return _graph
    model = build_chat_model()
    try:
        from langchain.agents import create_agent

        _graph = create_agent(
            model=model,
            tools=TOOLS,
            system_prompt=SYSTEM,
            checkpointer=_checkpointer,
            name="jobhunter-supervisor",
        )
    except Exception:
        from langgraph.prebuilt import create_react_agent

        _graph = create_react_agent(
            model=model,
            tools=TOOLS,
            prompt=SYSTEM,
            checkpointer=_checkpointer,
            name="jobhunter-supervisor",
        )
    _graph_fingerprint = fp
    return _graph


async def run_chat(message: str, thread_id: str = "default") -> dict[str, Any]:
    import logging
    logger = logging.getLogger("jobhunter")
    token = thread_id_var.set(thread_id)
    logger.info(f"[run_chat] start  thread={thread_id} msg_len={len(message)}")
    graph = get_graph()
    logger.info("[run_chat] graph ready")
    config = {"configurable": {"thread_id": thread_id}}
    bus.emit(thread_id, "status", {"message": "thinking"})
    try:
        logger.info("[run_chat] calling graph.ainvoke...")
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=config,
        )
        logger.info(f"[run_chat] ainvoke done  messages={len(result.get('messages', []))}")
        messages = result.get("messages") or []
        text = ""
        if messages:
            last = messages[-1]
            text = getattr(last, "content", "") or str(last)
        logger.info(f"[run_chat] emitting assistant  text_len={len(text)}")
        bus.emit(thread_id, "assistant", {"content": text})
        return {"content": text}
    except Exception as exc:  # noqa: BLE001
        err = f"模型调用失败：{exc}"
        logger.error(f"[run_chat] error: {exc}")
        bus.emit(thread_id, "error", {"message": err})
        return {"content": err, "error": True}
    finally:
        thread_id_var.reset(token)
        bus.close(thread_id)
        logger.info("[run_chat] done")


def has_model_config() -> bool:
    s = load_settings()
    if s.provider == "ollama":
        return True
    return bool(s.api_key)
