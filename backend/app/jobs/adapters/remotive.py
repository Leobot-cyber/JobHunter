from __future__ import annotations

import httpx

from app.jobs.textutil import keyword_hit, make_id, strip_html
from app.schemas import Job

HEADERS = {"User-Agent": "JobHunter-Learning-Agent/1.0 (educational)"}


class RemotiveAdapter:
    name = "remotive"
    display_name = "Remotive"

    async def search(self, keywords: list[str], location: str, limit: int) -> list[Job]:
        query = " ".join(keywords)
        params: dict[str, str | int] = {"limit": min(limit, 50)}
        if query:
            params["search"] = query
        async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
            resp = await client.get("https://remotive.com/api/remote-jobs", params=params)
            resp.raise_for_status()
            data = resp.json()
        jobs: list[Job] = []
        for item in data.get("jobs", []):
            title = item.get("title") or ""
            company = item.get("company_name") or ""
            loc = item.get("candidate_required_location") or "Remote"
            desc = strip_html(item.get("description") or "")
            hay = " ".join([title, company, loc, desc])
            if location and location.lower() not in hay.lower():
                continue
            if keywords and not keyword_hit(hay, keywords):
                continue
            jobs.append(
                Job(
                    id=make_id("remotive", str(item.get("id")), title, company),
                    source="remotive",
                    title=title,
                    company=company,
                    location=loc,
                    url=item.get("url") or "",
                    salary=item.get("salary") or "",
                    job_type=item.get("job_type") or "",
                    tags=[item.get("category")] if item.get("category") else [],
                    published_at=item.get("publication_date") or "",
                    description=desc,
                )
            )
            if len(jobs) >= limit:
                break
        return jobs
