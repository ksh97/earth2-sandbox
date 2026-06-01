from __future__ import annotations

from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.services.forecast_job_view import with_job_links
from earth2_sandbox.schemas.jobs import ForecastJob


class GetForecastJob:
    def __init__(self, *, store: ForecastJobStore) -> None:
        self.store = store

    async def execute(self, job_id: str) -> ForecastJob:
        return with_job_links(await self.store.get(job_id))
