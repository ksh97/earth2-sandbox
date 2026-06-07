from __future__ import annotations

import asyncio
import inspect
from collections.abc import Callable
from typing import Any

from earth2_sandbox.application.ports.forecast_queue import ForecastQueue

ForecastQueueFactory = Callable[[], ForecastQueue]


class ForecastQueueContract:
    """Reusable behavior checks for ForecastQueue adapters."""

    def __init__(self, queue_factory: ForecastQueueFactory) -> None:
        self._queue_factory = queue_factory

    def test_dequeues_by_priority_then_fifo(self) -> None:
        async def scenario() -> list[str]:
            queue = self._queue_factory()
            try:
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
            finally:
                await _dispose_queue(queue)

        assert asyncio.run(scenario()) == [
            "00000000-0000-0000-0000-000000000002",
            "00000000-0000-0000-0000-000000000003",
            "00000000-0000-0000-0000-000000000001",
            "00000000-0000-0000-0000-000000000004",
        ]

    def test_deduplicates_pending_and_in_flight_jobs(self) -> None:
        async def scenario() -> tuple[bool, bool, bool]:
            queue = self._queue_factory()
            try:
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
                )
            finally:
                await _dispose_queue(queue)

        assert asyncio.run(scenario()) == (True, False, False)

    def test_allows_reenqueue_after_completion(self) -> None:
        async def scenario() -> tuple[bool, bool, bool]:
            queue = self._queue_factory()
            try:
                first = await queue.enqueue(job_id="00000000-0000-0000-0000-000000000001")
                item = await queue.dequeue()
                assert item is not None
                await queue.mark_completed(item)
                second = await queue.enqueue(job_id="00000000-0000-0000-0000-000000000001")
                second_item = await queue.dequeue()
                return (
                    first.enqueued,
                    second.enqueued,
                    second_item is not None and second_item.job_id == item.job_id,
                )
            finally:
                await _dispose_queue(queue)

        assert asyncio.run(scenario()) == (True, True, True)

    def test_mark_failed_without_requeue_removes_in_flight_item(self) -> None:
        async def scenario() -> tuple[bool, str | None]:
            queue = self._queue_factory()
            try:
                await queue.enqueue(job_id="00000000-0000-0000-0000-000000000001")
                item = await queue.dequeue()
                assert item is not None
                await queue.mark_failed(item, requeue=False)
                duplicate_after_failure = await queue.enqueue(
                    job_id="00000000-0000-0000-0000-000000000001"
                )
                dequeued = await queue.dequeue()
                return (
                    duplicate_after_failure.enqueued,
                    dequeued.job_id if dequeued else None,
                )
            finally:
                await _dispose_queue(queue)

        assert asyncio.run(scenario()) == (
            True,
            "00000000-0000-0000-0000-000000000001",
        )

    def test_can_requeue_failed_items(self) -> None:
        async def scenario() -> str | None:
            queue = self._queue_factory()
            try:
                await queue.enqueue(job_id="00000000-0000-0000-0000-000000000001")
                item = await queue.dequeue()
                assert item is not None

                await queue.mark_failed(item, requeue=True)
                requeued = await queue.dequeue()
                return requeued.job_id if requeued else None
            finally:
                await _dispose_queue(queue)

        assert asyncio.run(scenario()) == "00000000-0000-0000-0000-000000000001"


async def _dispose_queue(queue: Any) -> None:
    clear = getattr(queue, "clear", None)
    if clear is not None:
        await _maybe_await(clear())

    close = getattr(queue, "close", None)
    if close is not None:
        await _maybe_await(close())


async def _maybe_await(value: Any) -> None:
    if inspect.isawaitable(value):
        await value
