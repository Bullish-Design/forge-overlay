from __future__ import annotations

import asyncio

from forge_overlay.events import EventBroker


class TestEventBroker:
    async def test_publish_to_subscriber(self) -> None:
        broker = EventBroker()
        received: list[str] = []

        async def consumer() -> None:
            async for event in broker.subscribe():
                received.append(event)
                if len(received) >= 2:
                    break

        task = asyncio.create_task(consumer())
        await asyncio.sleep(0.01)

        broker.publish('{"type":"rebuilt"}')
        broker.publish('{"type":"rebuilt"}')

        await asyncio.wait_for(task, timeout=1.0)
        assert received == ['{"type":"rebuilt"}', '{"type":"rebuilt"}']

    async def test_no_subscribers(self) -> None:
        broker = EventBroker()
        broker.publish("test")
        assert broker.subscriber_count == 0

    async def test_subscriber_cleanup(self) -> None:
        broker = EventBroker()

        async def short_consumer() -> None:
            async for _event in broker.subscribe():
                break

        task = asyncio.create_task(short_consumer())
        await asyncio.sleep(0.01)
        assert broker.subscriber_count == 1

        broker.publish("done")
        await asyncio.wait_for(task, timeout=1.0)
        await asyncio.sleep(0)
        assert broker.subscriber_count == 0

    async def test_multiple_subscribers(self) -> None:
        broker = EventBroker()
        results_a: list[str] = []
        results_b: list[str] = []

        async def consumer(results: list[str]) -> None:
            async for event in broker.subscribe():
                results.append(event)
                break

        task_a = asyncio.create_task(consumer(results_a))
        task_b = asyncio.create_task(consumer(results_b))
        await asyncio.sleep(0.01)

        broker.publish("hello")
        await asyncio.wait_for(asyncio.gather(task_a, task_b), timeout=1.0)

        assert results_a == ["hello"]
        assert results_b == ["hello"]
