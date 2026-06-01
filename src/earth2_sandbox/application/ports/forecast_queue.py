from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from earth2_sandbox.domain.jobs.priority import (
    DEFAULT_FORECAST_JOB_PRIORITY,
    ForecastJobPriority,
)


@dataclass(frozen=True, slots=True)
class ForecastQueueItem:
    job_id: str
    priority: ForecastJobPriority = DEFAULT_FORECAST_JOB_PRIORITY
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class ForecastQueueEnqueueResult:
    item: ForecastQueueItem
    enqueued: bool


class ForecastQueue(Protocol):
    """Port for priority-ready, idempotent forecast job dispatch."""

    async def enqueue(
        self,
        *,
        job_id: str,
        priority: ForecastJobPriority = DEFAULT_FORECAST_JOB_PRIORITY,
        idempotency_key: str | None = None,
    ) -> ForecastQueueEnqueueResult: ...

    async def dequeue(self) -> ForecastQueueItem | None: ...

    async def mark_completed(self, item: ForecastQueueItem) -> None: ...

    async def mark_failed(
        self,
        item: ForecastQueueItem,
        *,
        requeue: bool = False,
    ) -> None: ...

