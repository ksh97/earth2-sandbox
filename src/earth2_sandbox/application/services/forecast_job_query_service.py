from __future__ import annotations

from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.services.forecast_job_view import (
    to_job_poll_response,
    to_job_summary,
    with_job_links,
)
from earth2_sandbox.domain.jobs.status import ForecastJobStatus
from earth2_sandbox.schemas.jobs import (
    ForecastJob,
    ForecastJobListResponse,
    ForecastJobPollResponse,
)


class ForecastJobQueryService:
    def __init__(self, *, store: ForecastJobStore) -> None:
        self.store = store

    async def get_job(self, job_id: str) -> ForecastJob:
        return with_job_links(await self.store.get(job_id))

    async def list_recent_jobs(
        self,
        *,
        limit: int,
        status: ForecastJobStatus | None = None,
    ) -> ForecastJobListResponse:
        jobs = await self.store.list_recent(limit=limit, status=status)
        summaries = [to_job_summary(with_job_links(job)) for job in jobs]
        return ForecastJobListResponse(count=len(summaries), jobs=summaries)

    async def poll_job(self, job_id: str) -> ForecastJobPollResponse:
        return to_job_poll_response(with_job_links(await self.store.get(job_id)))
