from __future__ import annotations

import asyncio
import heapq
from dataclasses import dataclass, field

from earth2_sandbox.application.ports.forecast_queue import (
    ForecastQueueEnqueueResult,
    ForecastQueueItem,
)
from earth2_sandbox.domain.jobs.priority import (
    DEFAULT_FORECAST_JOB_PRIORITY,
    ForecastJobPriority,
    priority_rank,
)


@dataclass(order=True, slots=True)
class _QueuedEntry:
    rank: int
    sequence: int
    item: ForecastQueueItem = field(compare=False)


class InMemoryPriorityForecastQueue:
    """Process-local priority queue with job-id idempotency.

    This adapter is intentionally small. It gives the application a stable
    queue contract without requiring Redis, a database, or a separate worker
    service before the job backend contract settles.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._entries: list[_QueuedEntry] = []
        self._queued_by_key: dict[str, ForecastQueueItem] = {}
        self._in_flight_by_key: dict[str, ForecastQueueItem] = {}
        self._sequence = 0

    async def enqueue(
        self,
        *,
        job_id: str,
        priority: ForecastJobPriority = DEFAULT_FORECAST_JOB_PRIORITY,
        idempotency_key: str | None = None,
    ) -> ForecastQueueEnqueueResult:
        key = _queue_key(job_id=job_id, idempotency_key=idempotency_key)
        async with self._lock:
            existing = self._queued_by_key.get(key) or self._in_flight_by_key.get(key)
            if existing is not None:
                return ForecastQueueEnqueueResult(item=existing, enqueued=False)

            item = ForecastQueueItem(
                job_id=job_id,
                priority=priority,
                idempotency_key=key,
            )
            entry = _QueuedEntry(
                rank=priority_rank(priority),
                sequence=self._next_sequence(),
                item=item,
            )
            self._queued_by_key[key] = item
            heapq.heappush(self._entries, entry)
            return ForecastQueueEnqueueResult(item=item, enqueued=True)

    async def dequeue(self) -> ForecastQueueItem | None:
        async with self._lock:
            while self._entries:
                entry = heapq.heappop(self._entries)
                key = _item_key(entry.item)
                queued = self._queued_by_key.get(key)
                if queued != entry.item:
                    continue

                del self._queued_by_key[key]
                self._in_flight_by_key[key] = entry.item
                return entry.item
            return None

    async def mark_completed(self, item: ForecastQueueItem) -> None:
        async with self._lock:
            self._in_flight_by_key.pop(_item_key(item), None)

    async def mark_failed(
        self,
        item: ForecastQueueItem,
        *,
        requeue: bool = False,
    ) -> None:
        async with self._lock:
            self._in_flight_by_key.pop(_item_key(item), None)

        if requeue:
            await self.enqueue(
                job_id=item.job_id,
                priority=item.priority,
                idempotency_key=item.idempotency_key,
            )

    async def pending_count(self) -> int:
        async with self._lock:
            return len(self._queued_by_key)

    async def in_flight_count(self) -> int:
        async with self._lock:
            return len(self._in_flight_by_key)

    def _next_sequence(self) -> int:
        sequence = self._sequence
        self._sequence += 1
        return sequence


def _queue_key(*, job_id: str, idempotency_key: str | None) -> str:
    return idempotency_key or job_id


def _item_key(item: ForecastQueueItem) -> str:
    return item.idempotency_key or item.job_id

