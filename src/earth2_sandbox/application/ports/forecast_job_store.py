from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Protocol

from earth2_sandbox.domain.jobs.status import ForecastJobStatus, ForecastJobTerminalStatus
from earth2_sandbox.schemas.jobs import ForecastJob


class ForecastJobStore(Protocol):
    async def create(
        self,
        *,
        latitude: float,
        longitude: float,
        parent_job_id: str | None = None,
        attempt: int = 1,
    ) -> ForecastJob: ...

    async def get(self, job_id: str) -> ForecastJob: ...

    async def update(self, job: ForecastJob) -> ForecastJob: ...

    async def update_if_status(
        self,
        job: ForecastJob,
        *,
        expected_statuses: Collection[ForecastJobStatus],
    ) -> ForecastJob: ...

    async def list_recent(
        self,
        *,
        limit: int,
        status: ForecastJobStatus | None = None,
    ) -> list[ForecastJob]: ...

    async def list_active(self) -> list[ForecastJob]: ...

    async def delete_older_than(
        self,
        *,
        cutoff: datetime,
        statuses: set[ForecastJobTerminalStatus],
    ) -> int: ...
