import asyncio

from earth2_sandbox.infrastructure.queue import InMemoryPriorityForecastQueue
from tests.forecast_queue_contract import ForecastQueueContract

IN_MEMORY_QUEUE_CONTRACT = ForecastQueueContract(InMemoryPriorityForecastQueue)


def test_in_memory_forecast_queue_dequeues_by_priority_then_fifo() -> None:
    IN_MEMORY_QUEUE_CONTRACT.test_dequeues_by_priority_then_fifo()


def test_in_memory_forecast_queue_deduplicates_pending_and_in_flight_jobs() -> None:
    IN_MEMORY_QUEUE_CONTRACT.test_deduplicates_pending_and_in_flight_jobs()


def test_in_memory_forecast_queue_allows_reenqueue_after_completion() -> None:
    IN_MEMORY_QUEUE_CONTRACT.test_allows_reenqueue_after_completion()


def test_in_memory_forecast_queue_marks_failed_items_without_requeue() -> None:
    IN_MEMORY_QUEUE_CONTRACT.test_mark_failed_without_requeue_removes_in_flight_item()


def test_in_memory_forecast_queue_can_requeue_failed_items() -> None:
    IN_MEMORY_QUEUE_CONTRACT.test_can_requeue_failed_items()


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

