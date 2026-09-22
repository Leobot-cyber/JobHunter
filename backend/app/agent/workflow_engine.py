from __future__ import annotations

import asyncio
import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.agent.events import bus
from app.agent.hunt_graph import heuristic_rank
from app.jobs.registry import search_jobs
from app.llm import build_chat_model
from app.schemas import Job
from app.store import upsert_jobs

Role = Literal["searcher", "ranker", "matcher", "reporter"]


class AgentSpec(BaseModel):
    role: Role = "searcher"
    prompt: str
    label: str = ""
    phase: str = ""


class WorkflowStep(BaseModel):
    op: Literal["agent", "parallel", "pipeline", "phase", "log"]
    title: str | None = None
    message: str | None = None
    agent: AgentSpec | None = None
    agents: list[AgentSpec] = Field(default_factory=list)
    stages: list[Role] = Field(default_factory=list)


class WorkflowMeta(BaseModel):
    name: str
    description: str
    whenToUse: str | None = None
    phases: list[str] = Field(default_factory=list)


class WorkflowPlan(BaseModel):
    meta: WorkflowMeta
    args: dict[str, Any] = Field(default_factory=dict)
    steps: list[WorkflowStep]


MAX_TOTAL_AGENTS = 8
MAX_CONCURRENT = 4


class WorkflowEngine:
    """DeepSeek-harness combinators, but as structured JSON instead of eval(JS).

    Vocabulary kept on purpose: agent / parallel / pipeline / phase / log.
    Structured plans are safer for a learning project and easier to observe.
    """

    def __init__(self, thread_id: str) -> None:
        self.thread_id = thread_id
        self.agents_started = 0
        self._jobs: list[dict[str, Any]] = []

    def emit(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        bus.emit(self.thread_id, event_type, payload)

    async def run(self, plan: WorkflowPlan) -> dict[str, Any]:
        self.emit("workflow/start", {"meta": plan.meta.model_dump()})
        ctx: dict[str, Any] = {"args": plan.args, "jobs": [], "notes": []}
        try:
            for step in plan.steps:
                await self._exec_step(step, ctx)
            self.emit(
                "workflow/end",
                {"stopReason": "completed", "agentsStarted": self.agents_started},
            )
            return {
                "stopReason": "completed",
                "agentsStarted": self.agents_started,
                "jobs": ctx.get("jobs") or [],
                "notes": ctx.get("notes") or [],
            }
        except Exception as exc:  # noqa: BLE001
            self.emit(
                "workflow/end",
                {"stopReason": "error", "error": str(exc), "agentsStarted": self.agents_started},
            )
            return {"stopReason": "error", "error": str(exc), "agentsStarted": self.agents_started}

    async def _exec_step(self, step: WorkflowStep, ctx: dict[str, Any]) -> None:
        if step.op == "phase":
            self.emit("workflow/phase", {"title": step.title or ""})
            return
        if step.op == "log":
            self.emit("workflow/log", {"message": step.message or ""})
            ctx["notes"].append(step.message or "")
            return
        if step.op == "agent":
            if not step.agent:
                raise ValueError("agent step missing spec")
            ctx["jobs"] = await self._agent(step.agent, ctx)
            return
        if step.op == "parallel":
            sem = asyncio.Semaphore(MAX_CONCURRENT)

            async def one(spec: AgentSpec) -> list[dict[str, Any]]:
                async with sem:
                    return await self._agent(spec, ctx)

            parts = await asyncio.gather(*[one(spec) for spec in step.agents])
            merged: list[dict[str, Any]] = []
            seen: set[str] = set()
            for chunk in parts:
                for job in chunk:
                    if job["id"] in seen:
                        continue
                    seen.add(job["id"])
                    merged.append(job)
            ctx["jobs"] = merged
            upsert_jobs([Job.model_validate(j) for j in merged])
            self.emit("jobs", {"jobs": merged})
            return
        if step.op == "pipeline":
            jobs = ctx.get("jobs") or []
            query = str((ctx.get("args") or {}).get("query") or "")
            for role in step.stages:
                spec = AgentSpec(role=role, prompt=query, label=role, phase=role)
                jobs = await self._agent(spec, {**ctx, "jobs": jobs})
                ctx["jobs"] = jobs
            return

    async def _agent(self, spec: AgentSpec, ctx: dict[str, Any]) -> list[dict[str, Any]]:
        if self.agents_started >= MAX_TOTAL_AGENTS:
            raise RuntimeError("maxTotalAgents exceeded")
        self.agents_started += 1
        seq = self.agents_started
        label = spec.label or spec.role
        self.emit(
            "workflow/agent-start",
            {"seq": seq, "label": label, "phase": spec.phase, "role": spec.role},
        )
        jobs: list[dict[str, Any]]
        if spec.role == "searcher":
            found = await search_jobs(spec.prompt, limit=20)
            jobs = [j.model_dump() for j in found]
        elif spec.role == "ranker":
            keys = [w for w in spec.prompt.replace(",", " ").split() if w]
            jobs = heuristic_rank(ctx.get("jobs") or [], keys)
        elif spec.role == "matcher":
            jobs = await llm_match(spec.prompt, ctx.get("jobs") or [])
        elif spec.role == "reporter":
            jobs = ctx.get("jobs") or []
            self.emit("workflow/log", {"message": f"reporter sees {len(jobs)} jobs"})
        else:
            jobs = ctx.get("jobs") or []
        upsert_jobs([Job.model_validate(j) for j in jobs]) if jobs else None
        self.emit("jobs", {"jobs": jobs})
        self.emit(
            "workflow/agent-end",
            {"seq": seq, "label": label, "phase": spec.phase, "role": spec.role, "count": len(jobs)},
        )
        return jobs


async def llm_match(criteria: str, jobs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not jobs:
        return []
    try:
        model = build_chat_model()
        payload = [
            {
                "id": j["id"],
                "title": j["title"],
                "company": j["company"],
                "location": j.get("location"),
                "tags": j.get("tags"),
                "snippet": (j.get("description") or "")[:280],
            }
            for j in jobs[:18]
        ]
        msg = await model.ainvoke(
            [
                (
                    "system",
                    "你是求职匹配官。根据用户标准给岗位打 0-1 分，返回 JSON 数组："
                    '[{"id":"...","score":0.8,"reasons":["..."]}]，不要 markdown。',
                ),
                ("human", f"标准：{criteria}\n岗位：{json.dumps(payload, ensure_ascii=False)}"),
            ]
        )
        text = getattr(msg, "content", "") or "[]"
        start, end = text.find("["), text.rfind("]")
        parsed = json.loads(text[start : end + 1]) if start >= 0 else []
        by_id = {item["id"]: item for item in parsed if "id" in item}
        out = []
        for job in jobs:
            extra = by_id.get(job["id"])
            if extra:
                job = {
                    **job,
                    "score": float(extra.get("score") or job.get("score") or 0),
                    "match_reasons": extra.get("reasons") or job.get("match_reasons") or [],
                }
            out.append(job)
        out.sort(key=lambda j: j.get("score") or 0, reverse=True)
        return out
    except Exception:
        keys = [w for w in criteria.replace(",", " ").split() if w]
        return heuristic_rank(jobs, keys)


def default_hunt_plan(query: str, location: str = "") -> WorkflowPlan:
    return WorkflowPlan(
        meta=WorkflowMeta(
            name="job-hunt",
            description="Search, rank, and match jobs across public boards",
            phases=["search", "rank", "match", "report"],
        ),
        args={"query": query, "location": location},
        steps=[
            WorkflowStep(op="phase", title="search"),
            WorkflowStep(
                op="parallel",
                agents=[
                    AgentSpec(role="searcher", prompt=query, label="board-search", phase="search"),
                ],
            ),
            WorkflowStep(op="phase", title="rank"),
            WorkflowStep(op="pipeline", stages=["ranker", "matcher"]),
            WorkflowStep(op="phase", title="report"),
            WorkflowStep(op="agent", agent=AgentSpec(role="reporter", prompt=query, label="report", phase="report")),
            WorkflowStep(op="log", message="hunt workflow finished"),
        ],
    )
