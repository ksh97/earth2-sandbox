from __future__ import annotations

import asyncio
from collections.abc import Callable

from earth2_sandbox.application.ports.forecast_job_worker import RunForecastJobCallback


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
