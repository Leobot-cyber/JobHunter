from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any


class EventBus:
    """Fan-out bus so UI can stream DeepSeek-style workflow events."""

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict[str, Any] | None]] = {}

    def ensure(self, thread_id: str) -> asyncio.Queue[dict[str, Any] | None]:
        if thread_id not in self._queues:
            self._queues[thread_id] = asyncio.Queue()
        return self._queues[thread_id]

    def emit(self, thread_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        q = self.ensure(thread_id)
        q.put_nowait({"type": event_type, "payload": payload or {}})

    def close(self, thread_id: str) -> None:
        self.ensure(thread_id).put_nowait(None)

    async def subscribe(self, thread_id: str) -> AsyncIterator[str]:
        q = self.ensure(thread_id)
        while True:
            item = await q.get()
            if item is None:
                break
            yield json.dumps(item, ensure_ascii=False)


bus = EventBus()
