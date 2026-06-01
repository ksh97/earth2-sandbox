from __future__ import annotations

import asyncio
from collections.abc import Callable

from earth2_sandbox.application.ports.forecast_job_worker import RunForecastJobCallback
from earth2_sandbox.application.ports.forecast_queue import ForecastQueue
from earth2_sandbox.domain.jobs.priority import (
    DEFAULT_FORECAST_JOB_PRIORITY,
    ForecastJobPriority,
)


class DeferredForecastJobWorker:
    """Schedules jobs through a framework-provided deferred task hook."""

    def __init__(
        self,
        *,
        add_task: Callable[[RunForecastJobCallback, str], object],
        run_job: RunForecastJobCallback,
    ) -> None:
        self._add_task = add_task
        self._run_job = run_job

    def enqueue(self, job_id: str) -> None:
        self._add_task(self._run_job, job_id)


class AsyncioTaskForecastJobWorker:
    """Schedules jobs on the current event loop for startup recovery."""

    def __init__(
        self,
        *,
        run_job: RunForecastJobCallback,
        tasks: set[asyncio.Task[None]] | None = None,
    ) -> None:
        self._run_job = run_job
        self._tasks = tasks if tasks is not None else set()

    def enqueue(self, job_id: str) -> None:
        task = asyncio.create_task(self._run_job(job_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)


class QueuedDeferredForecastJobWorker:
    """Queues jobs before running them through a deferred task hook."""

    def __init__(
        self,
        *,
        add_task: Callable[[Callable[[str], object], str], object],
        run_job: RunForecastJobCallback,
        queue: ForecastQueue,
        priority: ForecastJobPriority = DEFAULT_FORECAST_JOB_PRIORITY,
    ) -> None:
        self._add_task = add_task
        self._run_job = run_job
        self._queue = queue
        self._priority = priority

    def enqueue(self, job_id: str) -> None:
        self._add_task(self._enqueue_and_drain, job_id)

    async def _enqueue_and_drain(self, job_id: str) -> None:
        result = await self._queue.enqueue(
            job_id=job_id,
            priority=self._priority,
            idempotency_key=job_id,
        )
        if not result.enqueued:
            return
        await _drain_queue(queue=self._queue, run_job=self._run_job)


class QueuedAsyncioTaskForecastJobWorker:
    """Queues jobs and schedules queue draining on the current event loop."""

    def __init__(
        self,
        *,
        run_job: RunForecastJobCallback,
        queue: ForecastQueue,
        tasks: set[asyncio.Task[None]] | None = None,
        priority: ForecastJobPriority = DEFAULT_FORECAST_JOB_PRIORITY,
    ) -> None:
        self._run_job = run_job
        self._queue = queue
        self._tasks = tasks if tasks is not None else set()
        self._priority = priority

    def enqueue(self, job_id: str) -> None:
        task = asyncio.create_task(self._enqueue_and_drain(job_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _enqueue_and_drain(self, job_id: str) -> None:
        result = await self._queue.enqueue(
            job_id=job_id,
            priority=self._priority,
            idempotency_key=job_id,
        )
        if not result.enqueued:
            return
        await _drain_queue(queue=self._queue, run_job=self._run_job)


async def _drain_queue(
    *,
    queue: ForecastQueue,
    run_job: RunForecastJobCallback,
) -> None:
    while True:
        item = await queue.dequeue()
        if item is None:
            return

        try:
            await run_job(item.job_id)
        except Exception:
            await queue.mark_failed(item, requeue=False)
            raise
        await queue.mark_completed(item)
