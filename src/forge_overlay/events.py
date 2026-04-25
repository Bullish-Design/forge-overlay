from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator


class EventBroker:
    """Pub/sub broker for server-sent events."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[str]] = set()

    def publish(self, data: str) -> None:
        """Send an event to all connected subscribers."""
        for queue in self._subscribers:
            queue.put_nowait(data)

    async def subscribe(self) -> AsyncGenerator[str]:
        """Yield events as they arrive. Use as `async for event in broker.subscribe()`."""
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._subscribers.add(queue)
        try:
            while True:
                data = await queue.get()
                yield data
        finally:
            self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
