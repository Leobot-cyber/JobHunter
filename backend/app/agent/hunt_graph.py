from __future__ import annotations

from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.jobs.registry import search_jobs
from app.jobs.textutil import split_keywords
from app.schemas import Job
from app.store import upsert_jobs


class HuntState(TypedDict):
    query: str
    location: str
    sources: list[str]
    keywords: list[str]
    jobs: list[dict[str, Any]]
    report: str
    thread_id: str


def _emit(state: HuntState, event_type: str, payload: dict[str, Any] | None = None) -> None:
    from app.agent.events import bus

    bus.emit(state.get("thread_id") or "default", event_type, payload)


def parse_intent(state: HuntState) -> dict[str, Any]:
    _emit(state, "workflow/start", {"meta": {"name": "job-hunt", "description": "deterministic hunt pipeline"}})
    _emit(state, "workflow/phase", {"title": "plan"})
    keys = split_keywords(state["query"])
    _emit(state, "workflow/log", {"message": f"keywords={keys} location={state.get('location') or '*'}"})
    return {"keywords": keys}


async def fetch_jobs(state: HuntState) -> dict[str, Any]:
    _emit(state, "workflow/phase", {"title": "search"})
    _emit(
        state,
        "workflow/agent-start",
        {"label": "searcher", "phase": "search", "seq": 1},
    )
    jobs = await search_jobs(
        keywords=state["query"],
        location=state.get("location") or "",
        sources=state.get("sources") or None,
        limit=40,
    )
    upsert_jobs(jobs)
    _emit(
        state,
        "workflow/agent-end",
        {"label": "searcher", "phase": "search", "seq": 1, "count": len(jobs)},
    )
    _emit(state, "jobs", {"jobs": [j.model_dump() for j in jobs]})
    return {"jobs": [j.model_dump() for j in jobs]}


def heuristic_rank(jobs: list[dict[str, Any]], keywords: list[str]) -> list[dict[str, Any]]:
    lowered = [k.lower() for k in keywords]
    ranked: list[dict[str, Any]] = []
    for job in jobs:
        hay = " ".join(
            [
                job.get("title") or "",
                job.get("company") or "",
                job.get("location") or "",
                " ".join(job.get("tags") or []),
                (job.get("description") or "")[:400],
            ]
        ).lower()
        hits = [k for k in lowered if k in hay]
        score = min(1.0, 0.35 + 0.15 * len(hits) + (0.1 if job.get("salary") else 0))
        reasons = [f"命中关键词「{h}」" for h in hits[:4]]
        if job.get("salary"):
            reasons.append("包含薪资信息")
        job = {**job, "score": round(score, 2), "match_reasons": reasons or ["来源匹配，待人工确认"]}
        ranked.append(job)
    ranked.sort(key=lambda j: j.get("score") or 0, reverse=True)
    return ranked


def rank_node(state: HuntState) -> dict[str, Any]:
    _emit(state, "workflow/phase", {"title": "rank"})
    ranked = heuristic_rank(state.get("jobs") or [], state.get("keywords") or [])
    upsert_jobs([Job.model_validate(j) for j in ranked])
    _emit(state, "jobs", {"jobs": ranked})
    return {"jobs": ranked}


def report_node(state: HuntState) -> dict[str, Any]:
    _emit(state, "workflow/phase", {"title": "report"})
    jobs = state.get("jobs") or []
    top = jobs[:8]
    lines = [f"共检索到 {len(jobs)} 个岗位，按匹配度列出前 {len(top)} 个："]
    for i, job in enumerate(top, 1):
        reasons = "；".join(job.get("match_reasons") or [])
        lines.append(
            f"{i}. [{job.get('source')}] {job.get('title')} @ {job.get('company')} "
            f"({job.get('location') or 'n/a'})  score={job.get('score')}  {reasons}"
        )
    report = "\n".join(lines)
    _emit(state, "workflow/log", {"message": f"report ready, {len(jobs)} jobs"})
    _emit(state, "workflow/end", {"stopReason": "completed", "agentsStarted": 1})
    return {"report": report}


def build_hunt_graph():
    graph = StateGraph(HuntState)
    graph.add_node("plan", parse_intent)
    graph.add_node("search", fetch_jobs)
    graph.add_node("rank", rank_node)
    graph.add_node("report", report_node)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "search")
    graph.add_edge("search", "rank")
    graph.add_edge("rank", "report")
    graph.add_edge("report", END)
    return graph.compile()


hunt_graph = build_hunt_graph()
