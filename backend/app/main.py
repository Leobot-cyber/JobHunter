from __future__ import annotations

import asyncio
import json
import httpx

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from app.agent.events import bus
from app.agent.supervisor import has_model_config, run_chat
from app.jobs.registry import list_sources, search_jobs
from app.llm import PROVIDERS, mask_key
from app.schemas import ChatRequest, SearchRequest, SettingsUpdate
from app.settings import load_settings, save_settings
from app.store import list_jobs, set_saved, upsert_jobs

app = FastAPI(title="JobHunter Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"ok": True}


@app.get("/api/providers")
def providers():
    return {"providers": PROVIDERS, "sources": list_sources()}


@app.get("/api/settings")
def get_settings():
    s = load_settings()
    data = s.model_dump()
    data["api_key_masked"] = mask_key(s.api_key)
    data["api_key_set"] = bool(s.api_key)
    data["api_key"] = ""
    data["has_model"] = has_model_config()
    return data


@app.put("/api/settings")
def update_settings(body: SettingsUpdate):
    current = load_settings()
    patch = body.model_dump(exclude_none=True)
    if "api_key" in patch and not patch["api_key"]:
        patch.pop("api_key")
    updated = current.model_copy(update=patch)
    save_settings(updated)
    from app.agent import supervisor

    supervisor._graph = None
    return get_settings()


@app.get("/api/jobs")
def jobs():
    return {"jobs": [j.model_dump() for j in list_jobs()]}


@app.post("/api/jobs/search")
async def jobs_search(body: SearchRequest):
    found = await search_jobs(
        keywords=body.keywords,
        location=body.location,
        sources=body.sources,
        limit=body.limit,
    )
    upsert_jobs(found)
    return {"jobs": [j.model_dump() for j in found]}


@app.post("/api/jobs/{job_id}/save")
def save(job_id: str, saved: bool = True):
    job = set_saved(job_id, saved)
    if not job:
        raise HTTPException(404, "job not found")
    return job.model_dump()


@app.post("/api/chat")
async def chat(body: ChatRequest):
    if not has_model_config():
        raise HTTPException(400, "请先在设置里填写模型 API Key，或改用 Ollama")
    result = await run_chat(body.message, body.thread_id)
    return result


@app.post("/api/chat/stream")
async def chat_stream(body: ChatRequest):
    if not has_model_config():
        raise HTTPException(400, "请先在设置里填写模型 API Key，或改用 Ollama")

    async def gen():
        # Collect all events first, then yield them one by one.
        # This avoids the race condition where bus.close() puts None
        # into the queue before the generator reads the assistant event.
        collected: list[str] = []

        async def collector():
            async for payload in bus.subscribe(body.thread_id):
                collected.append(payload)

        task = asyncio.create_task(run_chat(body.message, body.thread_id))
        await collector()  # blocks until bus.close() sends None
        try:
            await task
        except Exception as exc:  # noqa: BLE001
            collected.append(json.dumps({"type": "error", "payload": {"message": str(exc)}}))

        for payload in collected:
            yield {"event": "agent", "data": payload}

    return EventSourceResponse(gen())


# ── Ollama 模型管理 ──

@app.get("/api/ollama/models")
async def list_ollama_models():
    """列出 Ollama 已安装的模型"""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get("http://localhost:11434/api/tags", timeout=5)
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                models.append({
                    "name": m["name"],
                    "size": m.get("size", 0),
                    "modified_at": m.get("modified_at", ""),
                })
            return {"models": models}
    except Exception as e:
        raise HTTPException(503, f"Ollama 服务不可用: {e}")


@app.post("/api/ollama/pull")
async def pull_ollama_model(body: dict):
    """拉取指定模型"""
    model_name = body.get("model", "")
    if not model_name:
        raise HTTPException(400, "请指定模型名称")

    async def generate():
        try:
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    "POST",
                    "http://localhost:11434/api/pull",
                    json={"name": model_name, "stream": True},
                    timeout=600,
                ) as resp:
                    async for line in resp.aiter_lines():
                        if line.strip():
                            yield {"event": "pull", "data": line}
        except Exception as e:
            yield {"event": "error", "data": json.dumps({"error": str(e)})}

    return EventSourceResponse(generate())
