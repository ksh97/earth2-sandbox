from __future__ import annotations

from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.services.forecast_job_view import to_job_summary, with_job_links
from earth2_sandbox.domain.jobs.status import ForecastJobStatus
from earth2_sandbox.schemas.jobs import ForecastJobListResponse


class ListForecastJobs:
    def __init__(self, *, store: ForecastJobStore) -> None:
        self.store = store

    async def execute(
        self,
        *,
        limit: int,
        status: ForecastJobStatus | None = None,
    ) -> ForecastJobListResponse:
        jobs = await self.store.list_recent(limit=limit, status=status)
        summaries = [to_job_summary(with_job_links(job)) for job in jobs]
        return ForecastJobListResponse(count=len(summaries), jobs=summaries)
