import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from earth2_sandbox.application.commands import (
    CancelForecastJob,
    CleanupForecastJobs,
    RetryForecastJob,
    RunForecastJob,
    SubmitForecastJob,
)
from earth2_sandbox.application.errors import ForecastJobConflictError
from earth2_sandbox.application.queries import GetForecastJob, ListForecastJobs, PollForecastJob
from earth2_sandbox.infrastructure.storage import FileForecastJobStore, InMemoryForecastJobStore
from earth2_sandbox.providers import MockForecastProvider


def test_submit_list_get_and_poll_forecast_job_use_cases() -> None:
    async def scenario():
        store = InMemoryForecastJobStore()
        submit = SubmitForecastJob(store=store)
        get_job = GetForecastJob(store=store)
        list_jobs = ListForecastJobs(store=store)
        poll_job = PollForecastJob(store=store)

        created = await submit.execute(latitude=37.5665, longitude=126.9780)
        loaded = await get_job.execute(created.id)
        listed = await list_jobs.execute(limit=5)
        polled = await poll_job.execute(created.id)

        return created, loaded, listed, polled

    created, loaded, listed, polled = asyncio.run(scenario())

    assert created.status == "queued"
    assert loaded.links["self"] == f"/api/v1/forecast/jobs/{created.id}"
    assert listed.count == 1
    assert listed.jobs[0].id == created.id
    assert polled.status == "queued"
    assert polled.terminal is False


def test_cancel_and_retry_forecast_job_use_cases() -> None:
    async def scenario():
        store = InMemoryForecastJobStore()
        submit = SubmitForecastJob(store=store)
        cancel = CancelForecastJob(store=store)
        retry = RetryForecastJob(store=store)

        queued = await submit.execute(latitude=37.5665, longitude=126.9780)
        cancelled = await cancel.execute(queued.id)
        retry_job = await retry.execute(cancelled.id)

        with pytest.raises(ForecastJobConflictError):
            await retry.execute(retry_job.id)

        return queued, cancelled, retry_job

    queued, cancelled, retry_job = asyncio.run(scenario())

    assert cancelled.status == "cancelled"
    assert cancelled.events[-1].message == "Forecast job cancelled by request."
    assert retry_job.parent_job_id == queued.id
    assert retry_job.attempt == 2


def test_run_forecast_job_use_case_records_success() -> None:
    async def scenario():
        store = InMemoryForecastJobStore()
        submit = SubmitForecastJob(store=store)
        run = RunForecastJob(provider=MockForecastProvider(), store=store)

        queued = await submit.execute(latitude=37.5665, longitude=126.9780)
        await run.execute(queued.id)
        return await store.get(queued.id)

    completed = asyncio.run(scenario())

    assert completed.status == "succeeded"
    assert completed.forecast is not None
    assert [event.status for event in completed.events] == ["queued", "running", "succeeded"]


def test_cleanup_forecast_jobs_use_case_deletes_old_terminal_jobs(tmp_path) -> None:
    async def scenario():
        store = FileForecastJobStore(tmp_path)
        cleanup = CleanupForecastJobs(store=store, default_retention_hours=168)
        old_job = await store.create(latitude=37.5665, longitude=126.9780)
        fresh_job = await store.create(latitude=35.6762, longitude=139.6503)

        old_time = datetime.now(UTC) - timedelta(hours=200)
        old_terminal = old_job.model_copy(
            update={
                "status": "succeeded",
                "updated_at": old_time,
                "completed_at": old_time,
            }
        )
        (tmp_path / f"{old_job.id}.json").write_text(
            old_terminal.model_dump_json(indent=2),
            encoding="utf-8",
        )
        await store.update(fresh_job.model_copy(update={"status": "succeeded"}))

        cleanup_result = await cleanup.execute()
        remaining = await store.list_recent(limit=10)
        return cleanup_result, remaining

    cleanup_result, remaining = asyncio.run(scenario())

    assert cleanup_result.deleted_count == 1
    assert [job.latitude for job in remaining] == [35.6762]
