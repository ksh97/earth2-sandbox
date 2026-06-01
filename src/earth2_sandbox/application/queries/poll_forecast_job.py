from __future__ import annotations

from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.services.forecast_job_view import (
    to_job_poll_response,
    with_job_links,
)
from earth2_sandbox.schemas.jobs import ForecastJobPollResponse


class PollForecastJob:
    def __init__(self, *, store: ForecastJobStore) -> None:
        self.store = store

    async def execute(self, job_id: str) -> ForecastJobPollResponse:
        return to_job_poll_response(with_job_links(await self.store.get(job_id)))
