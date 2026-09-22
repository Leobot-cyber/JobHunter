from __future__ import annotations

import httpx

from app.jobs.textutil import keyword_hit, make_id, strip_html
from app.schemas import Job

HEADERS = {"User-Agent": "JobHunter-Learning-Agent/1.0 (educational)"}


class RemoteOKAdapter:
    name = "remoteok"
    display_name = "RemoteOK"

    async def search(self, keywords: list[str], location: str, limit: int) -> list[Job]:
        params = {}
        if keywords:
            params["tags"] = ",".join(k.lower().replace(" ", "-") for k in keywords[:4])
        async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
            resp = await client.get("https://remoteok.com/api", params=params)
            resp.raise_for_status()
            data = resp.json()
        jobs: list[Job] = []
        for item in data:
            if not isinstance(item, dict) or not item.get("position"):
                continue
            title = item.get("position") or ""
            company = item.get("company") or ""
            loc = item.get("location") or "Remote"
            tags = item.get("tags") or []
            desc = strip_html(item.get("description") or "")
            hay = " ".join([title, company, loc, desc, " ".join(map(str, tags))])
            if location and location.lower() not in hay.lower():
                continue
            if keywords and not keyword_hit(hay, keywords):
                continue
            salary = ""
            if item.get("salary_min") or item.get("salary_max"):
                salary = f"{item.get('salary_min') or '?'} - {item.get('salary_max') or '?'}"
            url = item.get("url") or item.get("apply_url") or ""
            jobs.append(
                Job(
                    id=make_id("remoteok", str(item.get("id")), title, company),
                    source="remoteok",
                    title=title,
                    company=company,
                    location=loc,
                    url=url,
                    salary=salary,
                    job_type="",
                    tags=[str(t) for t in tags][:8],
                    published_at=str(item.get("date") or item.get("epoch") or ""),
                    description=desc,
                )
            )
            if len(jobs) >= limit:
                break
        return jobs
