from __future__ import annotations

from typing import Protocol

from app.schemas import Job


class JobAdapter(Protocol):
    name: str
    display_name: str

    async def search(self, keywords: list[str], location: str, limit: int) -> list[Job]: ...
