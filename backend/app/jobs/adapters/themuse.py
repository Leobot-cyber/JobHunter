from __future__ import annotations

import httpx

from app.jobs.textutil import keyword_hit, make_id, strip_html
from app.schemas import Job

HEADERS = {"User-Agent": "JobHunter-Learning-Agent/1.0 (educational)"}


class TheMuseAdapter:
    name = "themuse"
    display_name = "The Muse"

    async def search(self, keywords: list[str], location: str, limit: int) -> list[Job]:
        params: dict[str, str | int] = {"page": 0, "descending": "true"}
        if location:
            params["location"] = location
        jobs: list[Job] = []
        async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
            for page in range(0, 3):
                params["page"] = page
                resp = await client.get("https://www.themuse.com/api/public/jobs", params=params)
                resp.raise_for_status()
                data = resp.json()
                items = data.get("results") or []
                if not items:
                    break
                for item in items:
                    title = item.get("name") or ""
                    company = (item.get("company") or {}).get("name") or ""
                    locs = [l.get("name") for l in item.get("locations") or [] if l.get("name")]
                    loc = ", ".join(locs)
                    cats = [c.get("name") for c in item.get("categories") or [] if c.get("name")]
                    levels = [lv.get("name") for lv in item.get("levels") or [] if lv.get("name")]
                    desc = strip_html(item.get("contents") or "")
                    hay = " ".join([title, company, loc, desc, " ".join(cats)])
                    if keywords and not keyword_hit(hay, keywords):
                        continue
                    jobs.append(
                        Job(
                            id=make_id("themuse", str(item.get("id")), title, company),
                            source="themuse",
                            title=title,
                            company=company,
                            location=loc or "Flexible",
                            url=item.get("refs", {}).get("landing_page") or "",
                            salary="",
                            job_type=", ".join(levels),
                            tags=cats[:8],
                            published_at=item.get("publication_date") or "",
                            description=desc,
                        )
                    )
                    if len(jobs) >= limit:
                        return jobs
        return jobs
