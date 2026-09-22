from __future__ import annotations

import asyncio

from app.jobs.adapters.arbeitnow import ArbeitnowAdapter
from app.jobs.adapters.remoteok import RemoteOKAdapter
from app.jobs.adapters.remotive import RemotiveAdapter
from app.jobs.adapters.themuse import TheMuseAdapter
from app.jobs.textutil import split_keywords
from app.schemas import Job
from app.settings import load_settings

ADAPTERS = {
    "remotive": RemotiveAdapter(),
    "remoteok": RemoteOKAdapter(),
    "arbeitnow": ArbeitnowAdapter(),
    "themuse": TheMuseAdapter(),
}


def list_sources() -> list[dict[str, str]]:
    return [{"id": a.name, "label": a.display_name} for a in ADAPTERS.values()]


async def search_jobs(
    keywords: str,
    location: str = "",
    sources: list[str] | None = None,
    limit: int = 30,
) -> list[Job]:
    settings = load_settings()
    selected = sources or settings.sources
    selected = [s for s in selected if s in ADAPTERS]
    if not selected:
        selected = list(ADAPTERS.keys())
    keys = split_keywords(keywords)
    per_source = max(8, limit // max(len(selected), 1))

    async def run(name: str) -> tuple[str, list[Job] | Exception]:
        try:
            jobs = await ADAPTERS[name].search(keys, location, per_source)
            return name, jobs
        except Exception as exc:  # noqa: BLE001 — keep one source from killing the hunt
            return name, exc

    pairs = await asyncio.gather(*[run(name) for name in selected])
    merged: list[Job] = []
    seen: set[tuple[str, str]] = set()
    errors: list[str] = []
    for name, result in pairs:
        if isinstance(result, Exception):
            errors.append(f"{name}: {result}")
            continue
        for job in result:
            key = (job.company.lower(), job.title.lower())
            if key in seen:
                continue
            seen.add(key)
            merged.append(job)
    merged.sort(key=lambda j: j.published_at, reverse=True)
    return merged[:limit]
