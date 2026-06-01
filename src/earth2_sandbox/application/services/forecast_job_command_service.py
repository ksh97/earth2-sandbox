from __future__ import annotations

from earth2_sandbox.application.commands import (
    CancelForecastJob,
    CleanupForecastJobs,
    DiagnosticForecastProvider,
    RetryForecastJob,
    RunForecastJob,
    SubmitForecastJob,
)
from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.ports.forecast_provider import ForecastProvider
from earth2_sandbox.domain.jobs.status import ForecastJobTerminalStatus
from earth2_sandbox.schemas.jobs import ForecastJob, ForecastJobCleanupResponse

__all__ = [
    "DiagnosticForecastProvider",
    "ForecastJobCommandService",
]


class ForecastJobCommandService:
    def __init__(
        self,
        *,
        provider: ForecastProvider,
        store: ForecastJobStore,
        default_retention_hours: int = 168,
    ) -> None:
        self.submit_forecast_job = SubmitForecastJob(store=store)
        self.cancel_forecast_job = CancelForecastJob(store=store)
        self.retry_forecast_job = RetryForecastJob(store=store)
        self.cleanup_forecast_jobs = CleanupForecastJobs(
            store=store,
            default_retention_hours=default_retention_hours,
        )
        self.run_forecast_job = RunForecastJob(provider=provider, store=store)

    async def create_job(self, *, latitude: float, longitude: float) -> ForecastJob:
        return await self.submit_forecast_job.execute(latitude=latitude, longitude=longitude)

    async def cancel_job(self, job_id: str) -> ForecastJob:
        return await self.cancel_forecast_job.execute(job_id)

    async def retry_job(self, job_id: str) -> ForecastJob:
        return await self.retry_forecast_job.execute(job_id)

    async def cleanup_jobs(
        self,
        *,
        older_than_hours: int | None = None,
        statuses: list[ForecastJobTerminalStatus] | None = None,
    ) -> ForecastJobCleanupResponse:
        return await self.cleanup_forecast_jobs.execute(
            older_than_hours=older_than_hours,
            statuses=statuses,
        )

    async def run_job(self, job_id: str) -> None:
        await self.run_forecast_job.execute(job_id)
