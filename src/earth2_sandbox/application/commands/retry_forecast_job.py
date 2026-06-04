from __future__ import annotations

from earth2_sandbox.application.errors import ForecastJobConflictError
from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.services.forecast_job_view import with_job_links
from earth2_sandbox.domain.jobs.status import TERMINAL_JOB_STATUSES
from earth2_sandbox.observability.metrics import increment_forecast_job_event
from earth2_sandbox.schemas.jobs import ForecastJob


class RetryForecastJob:
    def __init__(self, *, store: ForecastJobStore) -> None:
        self.store = store

    async def execute(self, job_id: str) -> ForecastJob:
        source = await self.store.get(job_id)
        if source.status not in TERMINAL_JOB_STATUSES:
            raise ForecastJobConflictError(f"Cannot retry a {source.status} forecast job.")

        retry = await self.store.create(
            latitude=source.latitude,
            longitude=source.longitude,
            parent_job_id=source.id,
            attempt=source.attempt + 1,
        )
        retry = with_job_links(retry)
        increment_forecast_job_event("retry_accepted")
        return retry
