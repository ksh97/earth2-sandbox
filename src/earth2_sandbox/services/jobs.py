from __future__ import annotations

from earth2_sandbox.application.errors import (
    ForecastJobConflictError,
    ForecastJobNotFoundError,
    ForecastJobTransitionError,
)
from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.ports.forecast_provider import ForecastProvider
from earth2_sandbox.application.services import (
    ForecastJobCommandService,
    ForecastJobQueryService,
    ForecastJobRecoveryReport,
    ForecastJobRecoveryService,
)
from earth2_sandbox.domain.jobs.status import ForecastJobStatus, ForecastJobTerminalStatus
from earth2_sandbox.infrastructure.storage import (
    FileForecastJobStore,
    InMemoryForecastJobStore,
)
from earth2_sandbox.schemas.jobs import (
    ForecastJob,
    ForecastJobCleanupResponse,
    ForecastJobListResponse,
    ForecastJobPollResponse,
)
from earth2_sandbox.workers import ForecastJobWorker

__all__ = [
    "FileForecastJobStore",
    "ForecastJobConflictError",
    "ForecastJobNotFoundError",
    "ForecastJobRecoveryReport",
    "ForecastJobService",
    "ForecastJobStore",
    "ForecastJobTransitionError",
    "InMemoryForecastJobStore",
]


class ForecastJobService:
    """Compatibility facade for the forecast job application services."""

    def __init__(
        self,
        *,
        provider: ForecastProvider,
        store: ForecastJobStore | None = None,
        default_retention_hours: int = 168,
        default_stale_timeout_seconds: int = 1800,
    ) -> None:
        self.provider = provider
        self.store = store or InMemoryForecastJobStore()
        self.default_retention_hours = default_retention_hours
        self.default_stale_timeout_seconds = default_stale_timeout_seconds
        self.command_service = ForecastJobCommandService(
            provider=self.provider,
            store=self.store,
            default_retention_hours=self.default_retention_hours,
        )
        self.query_service = ForecastJobQueryService(store=self.store)
        self.recovery_service = ForecastJobRecoveryService(
            store=self.store,
            default_stale_timeout_seconds=self.default_stale_timeout_seconds,
        )

    async def create_job(self, *, latitude: float, longitude: float) -> ForecastJob:
        return await self.command_service.create_job(latitude=latitude, longitude=longitude)

    async def get_job(self, job_id: str) -> ForecastJob:
        return await self.query_service.get_job(job_id)

    async def list_recent_jobs(
        self,
        *,
        limit: int,
        status: ForecastJobStatus | None = None,
    ) -> ForecastJobListResponse:
        return await self.query_service.list_recent_jobs(limit=limit, status=status)

    async def poll_job(self, job_id: str) -> ForecastJobPollResponse:
        return await self.query_service.poll_job(job_id)

    async def cancel_job(self, job_id: str) -> ForecastJob:
        return await self.command_service.cancel_job(job_id)

    async def retry_job(self, job_id: str) -> ForecastJob:
        return await self.command_service.retry_job(job_id)

    async def cleanup_jobs(
        self,
        *,
        older_than_hours: int | None = None,
        statuses: list[ForecastJobTerminalStatus] | None = None,
    ) -> ForecastJobCleanupResponse:
        return await self.command_service.cleanup_jobs(
            older_than_hours=older_than_hours,
            statuses=statuses,
        )

    async def recover_interrupted_jobs(
        self,
        *,
        worker: ForecastJobWorker,
        stale_timeout_seconds: int | None = None,
    ) -> ForecastJobRecoveryReport:
        return await self.recovery_service.recover_interrupted_jobs(
            worker=worker,
            stale_timeout_seconds=stale_timeout_seconds,
        )

    async def run_job(self, job_id: str) -> None:
        await self.command_service.run_job(job_id)
