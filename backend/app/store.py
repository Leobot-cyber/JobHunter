from __future__ import annotations

import json
from threading import Lock

from app.schemas import Job
from app.settings import DATA_DIR

JOBS_PATH = DATA_DIR / "jobs.json"
_lock = Lock()


def _read() -> list[Job]:
    if not JOBS_PATH.exists():
        return []
    raw = json.loads(JOBS_PATH.read_text())
    return [Job.model_validate(item) for item in raw]


def _write(jobs: list[Job]) -> None:
    JOBS_PATH.write_text(json.dumps([j.model_dump() for j in jobs], ensure_ascii=False, indent=2))


def list_jobs() -> list[Job]:
    with _lock:
        return _read()


def upsert_jobs(incoming: list[Job]) -> list[Job]:
    with _lock:
        current = {j.id: j for j in _read()}
        for job in incoming:
            prev = current.get(job.id)
            if prev:
                job.saved = prev.saved or job.saved
                if prev.score is not None and job.score is None:
                    job.score = prev.score
                if prev.match_reasons and not job.match_reasons:
                    job.match_reasons = prev.match_reasons
            current[job.id] = job
        jobs = sorted(current.values(), key=lambda j: (j.score is None, -(j.score or 0), j.title))
        _write(jobs)
        return jobs


def set_saved(job_id: str, saved: bool) -> Job | None:
    with _lock:
        jobs = _read()
        found = None
        for job in jobs:
            if job.id == job_id:
                job.saved = saved
                found = job
        if found:
            _write(jobs)
        return found


def get_job(job_id: str) -> Job | None:
    with _lock:
        for job in _read():
            if job.id == job_id:
                return job
        return None
