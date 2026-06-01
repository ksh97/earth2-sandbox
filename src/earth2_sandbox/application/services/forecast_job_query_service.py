from __future__ import annotations

from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.queries import GetForecastJob, ListForecastJobs, PollForecastJob
from earth2_sandbox.domain.jobs.status import ForecastJobStatus
from earth2_sandbox.schemas.jobs import (
    ForecastJob,
    ForecastJobListResponse,
    ForecastJobPollResponse,
)


class ForecastJobQueryService:
    def __init__(self, *, store: ForecastJobStore) -> None:
        self.get_forecast_job = GetForecastJob(store=store)
        self.list_forecast_jobs = ListForecastJobs(store=store)
        self.poll_forecast_job = PollForecastJob(store=store)

    async def get_job(self, job_id: str) -> ForecastJob:
        return await self.get_forecast_job.execute(job_id)

    async def list_recent_jobs(
        self,
        *,
        limit: int,
        status: ForecastJobStatus | None = None,
    ) -> ForecastJobListResponse:
        return await self.list_forecast_jobs.execute(limit=limit, status=status)

    async def poll_job(self, job_id: str) -> ForecastJobPollResponse:
        return await self.poll_forecast_job.execute(job_id)
