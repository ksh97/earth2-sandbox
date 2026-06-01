from __future__ import annotations

from datetime import timedelta

from earth2_sandbox.application.ports.clock import Clock
from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.domain.jobs.status import TERMINAL_JOB_STATUSES, ForecastJobTerminalStatus
from earth2_sandbox.schemas.jobs import ForecastJobCleanupResponse


class CleanupForecastJobs:
    def __init__(
        self,
        *,
        store: ForecastJobStore,
        clock: Clock,
        default_retention_hours: int = 168,
    ) -> None:
        self.store = store
        self.clock = clock
        self.default_retention_hours = default_retention_hours

    async def execute(
        self,
        *,
        older_than_hours: int | None = None,
        statuses: list[ForecastJobTerminalStatus] | None = None,
    ) -> ForecastJobCleanupResponse:
        retention_hours = older_than_hours or self.default_retention_hours
        cleanup_statuses = set(statuses or sorted(TERMINAL_JOB_STATUSES))
        cutoff = self.clock.now() - timedelta(hours=retention_hours)
        deleted_count = await self.store.delete_older_than(
            cutoff=cutoff,
            statuses=cleanup_statuses,
        )
        return ForecastJobCleanupResponse(
            deleted_count=deleted_count,
            cutoff=cutoff,
            statuses=sorted(cleanup_statuses),
        )
