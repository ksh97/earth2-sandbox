import asyncio

from earth2_sandbox.infrastructure.queue import (
    AsyncioTaskForecastJobWorker,
    DeferredForecastJobWorker,
)
from earth2_sandbox.workers import ForecastJobWorker, RunForecastJob


def test_deferred_forecast_job_worker_uses_deferred_task_hook() -> None:
    scheduled: list[tuple[RunForecastJob, str]] = []

    async def run_job(job_id: str) -> None:
        scheduled.append((run_job, job_id))

    def add_task(callback: RunForecastJob, job_id: str) -> None:
        scheduled.append((callback, job_id))

    worker = DeferredForecastJobWorker(add_task=add_task, run_job=run_job)
    worker.enqueue("job-1")

    assert scheduled == [(run_job, "job-1")]


def test_asyncio_task_forecast_job_worker_schedules_and_tracks_tasks() -> None:
    async def scenario() -> list[str]:
        completed: list[str] = []
        tasks: set[asyncio.Task[None]] = set()

        async def run_job(job_id: str) -> None:
            completed.append(job_id)

        worker: ForecastJobWorker = AsyncioTaskForecastJobWorker(run_job=run_job, tasks=tasks)
        worker.enqueue("job-2")

        assert len(tasks) == 1
        await asyncio.gather(*tasks)
        await asyncio.sleep(0)
        assert tasks == set()
        return completed

    assert asyncio.run(scenario()) == ["job-2"]
