from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Job(BaseModel):
    id: str
    source: str
    title: str
    company: str
    location: str = ""
    url: str
    salary: str = ""
    job_type: str = ""
    tags: list[str] = Field(default_factory=list)
    published_at: str = ""
    description: str = ""
    score: float | None = None
    match_reasons: list[str] = Field(default_factory=list)
    saved: bool = False


class ChatRequest(BaseModel):
    message: str
    thread_id: str = "default"


class SettingsUpdate(BaseModel):
    provider: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    model: str | None = None
    temperature: float | None = None
    sources: list[str] | None = None


class SearchRequest(BaseModel):
    keywords: str
    location: str = ""
    sources: list[str] | None = None
    limit: int = 30


class AgentEvent(BaseModel):
    type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


WorkflowOp = Literal["agent", "parallel", "pipeline", "phase", "log"]
