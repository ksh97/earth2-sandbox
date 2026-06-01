import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from earth2_sandbox.application.errors import ForecastJobConflictError
from earth2_sandbox.application.services import (
    ForecastJobCommandService,
    ForecastJobQueryService,
    ForecastJobRecoveryService,
)
from earth2_sandbox.infrastructure.storage import FileForecastJobStore, InMemoryForecastJobStore
from earth2_sandbox.providers import MockForecastProvider


def test_forecast_job_command_and_query_services_share_store() -> None:
    async def scenario():
        store = InMemoryForecastJobStore()
        command_service = ForecastJobCommandService(
            provider=MockForecastProvider(),
            store=store,
        )
        query_service = ForecastJobQueryService(store=store)

        queued = await command_service.create_job(latitude=37.5665, longitude=126.9780)
        queued_poll = await query_service.poll_job(queued.id)
        await command_service.run_job(queued.id)
        completed = await query_service.get_job(queued.id)

        return queued, queued_poll, completed

    queued, queued_poll, completed = asyncio.run(scenario())

    assert queued.status == "queued"
    assert queued_poll.status == "queued"
    assert queued_poll.terminal is False
    assert queued_poll.links["self"] == f"/api/v1/forecast/jobs/{queued.id}"
    assert completed.status == "succeeded"
    assert completed.forecast is not None
    assert [event.status for event in completed.events] == ["queued", "running", "succeeded"]


def test_forecast_job_command_service_rejects_retry_for_active_job() -> None:
    async def scenario() -> None:
        store = InMemoryForecastJobStore()
        command_service = ForecastJobCommandService(
            provider=MockForecastProvider(),
            store=store,
        )
        job = await command_service.create_job(latitude=37.5665, longitude=126.9780)
        with pytest.raises(ForecastJobConflictError):
            await command_service.retry_job(job.id)

    asyncio.run(scenario())


def test_forecast_job_recovery_service_requeues_running_jobs() -> None:
    class RecordingWorker:
        def __init__(self) -> None:
            self.job_ids: list[str] = []

        def enqueue(self, job_id: str) -> None:
            self.job_ids.append(job_id)

    async def scenario():
        store = InMemoryForecastJobStore()
        recovery_service = ForecastJobRecoveryService(
            store=store,
            default_stale_timeout_seconds=3600,
        )
        running = await store.create(latitude=37.5665, longitude=126.9780)
        await store.update_if_status(
            running.model_copy(update={"status": "running"}),
            expected_statuses={"queued"},
        )
        worker = RecordingWorker()

        report = await recovery_service.recover_interrupted_jobs(worker=worker)
        loaded = await store.get(running.id)

        return report, worker.job_ids, loaded

    report, job_ids, loaded = asyncio.run(scenario())

    assert report.scanned_count == 1
    assert report.requeued_count == 1
    assert report.timed_out_count == 0
    assert job_ids == [loaded.id]
    assert loaded.status == "queued"
    assert loaded.started_at is None
    assert loaded.events[-1].message == "Forecast job recovered for worker retry."


def test_forecast_job_recovery_service_times_out_stale_jobs(tmp_path) -> None:
    class RecordingWorker:
        def __init__(self) -> None:
            self.job_ids: list[str] = []

        def enqueue(self, job_id: str) -> None:
            self.job_ids.append(job_id)

    async def scenario():
        store = FileForecastJobStore(tmp_path)
        recovery_service = ForecastJobRecoveryService(
            store=store,
            default_stale_timeout_seconds=60,
        )
        job = await store.create(latitude=37.5665, longitude=126.9780)
        old_time = datetime.now(UTC) - timedelta(minutes=10)
        stale_running = job.model_copy(
            update={
                "status": "running",
                "started_at": old_time,
                "updated_at": old_time,
            }
        )
        (tmp_path / f"{job.id}.json").write_text(
            stale_running.model_dump_json(indent=2),
            encoding="utf-8",
        )
        worker = RecordingWorker()

        report = await recovery_service.recover_interrupted_jobs(worker=worker)
        loaded = await store.get(job.id)

        return report, worker.job_ids, loaded

    report, job_ids, loaded = asyncio.run(scenario())

    assert report.scanned_count == 1
    assert report.requeued_count == 0
    assert report.timed_out_count == 1
    assert job_ids == []
    assert loaded.status == "failed"
    assert loaded.error == "Forecast worker timed out after 60 seconds without progress."
