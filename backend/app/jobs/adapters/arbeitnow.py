from __future__ import annotations

import httpx

from app.jobs.textutil import keyword_hit, make_id, strip_html
from app.schemas import Job

HEADERS = {"User-Agent": "JobHunter-Learning-Agent/1.0 (educational)"}


class ArbeitnowAdapter:
    name = "arbeitnow"
    display_name = "Arbeitnow"

    async def search(self, keywords: list[str], location: str, limit: int) -> list[Job]:
        jobs: list[Job] = []
        page = 1
        async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
            while len(jobs) < limit and page <= 3:
                resp = await client.get(
                    "https://www.arbeitnow.com/api/job-board-api",
                    params={"page": page},
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("data") or []
                if not items:
                    break
                for item in items:
                    title = item.get("title") or ""
                    company = item.get("company_name") or ""
                    loc = item.get("location") or ""
                    tags = item.get("tags") or []
                    desc = strip_html(item.get("description") or "")
                    hay = " ".join([title, company, loc, desc, " ".join(map(str, tags))])
                    if location and location.lower() not in hay.lower():
                        continue
                    if keywords and not keyword_hit(hay, keywords):
                        continue
                    jobs.append(
                        Job(
                            id=make_id("arbeitnow", item.get("slug") or title, company),
                            source="arbeitnow",
                            title=title,
                            company=company,
                            location=loc,
                            url=item.get("url") or "",
                            salary="",
                            job_type="remote" if item.get("remote") else "",
                            tags=[str(t) for t in tags][:8],
                            published_at=str(item.get("created_at") or ""),
                            description=desc,
                        )
                    )
                    if len(jobs) >= limit:
                        break
                page += 1
        return jobs
