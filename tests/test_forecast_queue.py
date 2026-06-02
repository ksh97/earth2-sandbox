import asyncio

from earth2_sandbox.infrastructure.queue import InMemoryPriorityForecastQueue


def test_in_memory_forecast_queue_dequeues_by_priority_then_fifo() -> None:
    async def scenario() -> list[str]:
        queue = InMemoryPriorityForecastQueue()
        await queue.enqueue(
            job_id="00000000-0000-0000-0000-000000000001",
            priority="normal",
        )
        await queue.enqueue(
            job_id="00000000-0000-0000-0000-000000000002",
            priority="high",
        )
        await queue.enqueue(
            job_id="00000000-0000-0000-0000-000000000003",
            priority="high",
        )
        await queue.enqueue(
            job_id="00000000-0000-0000-0000-000000000004",
            priority="low",
        )

        dequeued: list[str] = []
        while item := await queue.dequeue():
            dequeued.append(item.job_id)
            await queue.mark_completed(item)
        return dequeued

    assert asyncio.run(scenario()) == [
        "00000000-0000-0000-0000-000000000002",
        "00000000-0000-0000-0000-000000000003",
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000004",
    ]


def test_in_memory_forecast_queue_deduplicates_pending_and_in_flight_jobs() -> None:
    async def scenario() -> tuple[bool, bool, bool, int, int]:
        queue = InMemoryPriorityForecastQueue()
        first = await queue.enqueue(job_id="00000000-0000-0000-0000-000000000001")
        duplicate_pending = await queue.enqueue(
            job_id="00000000-0000-0000-0000-000000000001"
        )
        item = await queue.dequeue()
        assert item is not None
        duplicate_in_flight = await queue.enqueue(
            job_id="00000000-0000-0000-0000-000000000001"
        )
        await queue.mark_completed(item)
        return (
            first.enqueued,
            duplicate_pending.enqueued,
            duplicate_in_flight.enqueued,
            await queue.pending_count(),
            await queue.in_flight_count(),
        )

    assert asyncio.run(scenario()) == (True, False, False, 0, 0)


def test_in_memory_forecast_queue_can_requeue_failed_items() -> None:
    async def scenario() -> tuple[str | None, int]:
        queue = InMemoryPriorityForecastQueue()
        await queue.enqueue(job_id="00000000-0000-0000-0000-000000000001")
        item = await queue.dequeue()
        assert item is not None

        await queue.mark_failed(item, requeue=True)
        requeued = await queue.dequeue()
        return requeued.job_id if requeued else None, await queue.in_flight_count()

    assert asyncio.run(scenario()) == ("00000000-0000-0000-0000-000000000001", 1)


def test_in_memory_forecast_queue_requeues_failed_items_without_holding_lock() -> None:
    async def scenario() -> tuple[bool | None, str | None, int]:
        queue = InMemoryPriorityForecastQueue()
        await queue.enqueue(job_id="00000000-0000-0000-0000-000000000001")
        item = await queue.dequeue()
        assert item is not None

        original_enqueue = queue.enqueue
        lock_was_held_during_requeue: bool | None = None

        async def enqueue_spy(**kwargs):
            nonlocal lock_was_held_during_requeue
            lock_was_held_during_requeue = queue._lock.locked()
            return await original_enqueue(**kwargs)

        queue.enqueue = enqueue_spy

        await asyncio.wait_for(queue.mark_failed(item, requeue=True), timeout=1)
        requeued = await queue.dequeue()
        return (
            lock_was_held_during_requeue,
            requeued.job_id if requeued else None,
            await queue.in_flight_count(),
        )

    assert asyncio.run(scenario()) == (
        False,
        "00000000-0000-0000-0000-000000000001",
        1,
    )

