from __future__ import annotations

import json
from contextvars import ContextVar

from langchain_core.tools import tool

from app.agent.events import bus
from app.agent.hunt_graph import hunt_graph
from app.agent.workflow_engine import WorkflowEngine, WorkflowPlan, default_hunt_plan
from app.jobs.registry import search_jobs
from app.store import get_job, set_saved, upsert_jobs

thread_id_var: ContextVar[str] = ContextVar("thread_id", default="default")


def _tid() -> str:
    return thread_id_var.get()


@tool
async def search_public_jobs(keywords: str, location: str = "", sources: str = "") -> str:
    """Search public job boards (Remotive, RemoteOK, Arbeitnow, The Muse) by keywords.

    sources is an optional comma-separated list of adapter ids.
    """
    source_list = [s.strip() for s in sources.split(",") if s.strip()] or None
    bus.emit(_tid(), "tool", {"name": "search_public_jobs", "keywords": keywords})
    jobs = await search_jobs(keywords=keywords, location=location, sources=source_list, limit=30)
    upsert_jobs(jobs)
    bus.emit(_tid(), "jobs", {"jobs": [j.model_dump() for j in jobs]})
    compact = [
        {
            "id": j.id,
            "source": j.source,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "salary": j.salary,
            "url": j.url,
            "tags": j.tags,
        }
        for j in jobs[:20]
    ]
    return json.dumps({"count": len(jobs), "jobs": compact}, ensure_ascii=False)


@tool
async def run_hunt_pipeline(query: str, location: str = "") -> str:
    """Run the deterministic LangGraph hunt pipeline: plan → search → rank → report.

    Use this when the user wants a full job hunt rather than a one-off search.
    """
    result = await hunt_graph.ainvoke(
        {
            "query": query,
            "location": location,
            "sources": [],
            "keywords": [],
            "jobs": [],
            "report": "",
            "thread_id": _tid(),
        }
    )
    return result.get("report") or json.dumps(result.get("jobs") or [], ensure_ascii=False)


@tool
async def run_workflow(query: str, location: str = "") -> str:
    """Run a DeepSeek-harness-style workflow: phase / parallel / pipeline / agent / log.

    Prefer this for multi-source orchestration with observable phases.
    """
    engine = WorkflowEngine(_tid())
    plan: WorkflowPlan = default_hunt_plan(query, location)
    result = await engine.run(plan)
    jobs = result.get("jobs") or []
    return json.dumps(
        {
            "stopReason": result.get("stopReason"),
            "agentsStarted": result.get("agentsStarted"),
            "job_count": len(jobs),
            "top": jobs[:10],
        },
        ensure_ascii=False,
    )


@tool
def get_job_detail(job_id: str) -> str:
    """Fetch a previously retrieved job by id, including description snippet."""
    job = get_job(job_id)
    if not job:
        return json.dumps({"error": "job not found", "id": job_id})
    return job.model_dump_json()


@tool
def save_job(job_id: str, saved: bool = True) -> str:
    """Mark a job as saved/favorite so it appears in the Jobs board."""
    job = set_saved(job_id, saved)
    if not job:
        return json.dumps({"error": "job not found", "id": job_id})
    bus.emit(_tid(), "jobs", {"jobs": [job.model_dump()]})
    return job.model_dump_json()


TOOLS = [search_public_jobs, run_hunt_pipeline, run_workflow, get_job_detail, save_job]
