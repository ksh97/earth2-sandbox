from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol

from earth2_sandbox.application.errors import ForecastJobConflictError, ForecastJobTransitionError
from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.ports.forecast_provider import (
    ForecastProvider,
    ForecastProviderResult,
    ForecastProviderUnavailableError,
)
from earth2_sandbox.application.services.forecast_job_view import append_job_event, with_job_links
from earth2_sandbox.domain.jobs.status import (
    ACTIVE_JOB_STATUSES,
    TERMINAL_JOB_STATUSES,
    ForecastJobTerminalStatus,
)
from earth2_sandbox.schemas.jobs import (
    ForecastJob,
    ForecastJobCleanupResponse,
    ForecastJobDiagnostics,
)


class DiagnosticForecastProvider(Protocol):
    async def get_point_forecast_with_diagnostics(
        self,
        latitude: float,
        longitude: float,
    ) -> ForecastProviderResult: ...


class ForecastJobCommandService:
    def __init__(
        self,
        *,
        provider: ForecastProvider,
        store: ForecastJobStore,
        default_retention_hours: int = 168,
    ) -> None:
        self.provider = provider
        self.store = store
        self.default_retention_hours = default_retention_hours

    async def create_job(self, *, latitude: float, longitude: float) -> ForecastJob:
        return with_job_links(await self.store.create(latitude=latitude, longitude=longitude))

    async def cancel_job(self, job_id: str) -> ForecastJob:
        job = await self.store.get(job_id)
        if job.status in TERMINAL_JOB_STATUSES:
            raise ForecastJobConflictError(f"Cannot cancel a {job.status} forecast job.")

        now = datetime.now(UTC)
        cancelled = append_job_event(
            job.model_copy(
                update={
                    "status": "cancelled",
                    "completed_at": now,
                    "diagnostics": ForecastJobDiagnostics(
                        provider=job.diagnostics.provider if job.diagnostics else None,
                        message="Forecast job cancelled by request.",
                    ),
                    "error": None,
                }
            ),
            status="cancelled",
            message="Forecast job cancelled by request.",
            occurred_at=now,
        )
        try:
            return with_job_links(
                await self.store.update_if_status(
                    cancelled,
                    expected_statuses=ACTIVE_JOB_STATUSES,
                )
            )
        except ForecastJobTransitionError as error:
            raise ForecastJobConflictError(
                f"Cannot cancel a {error.current_status} forecast job."
            ) from error

    async def retry_job(self, job_id: str) -> ForecastJob:
        source = await self.store.get(job_id)
        if source.status not in TERMINAL_JOB_STATUSES:
            raise ForecastJobConflictError(f"Cannot retry a {source.status} forecast job.")

        retry = await self.store.create(
            latitude=source.latitude,
            longitude=source.longitude,
            parent_job_id=source.id,
            attempt=source.attempt + 1,
        )
        return with_job_links(retry)

    async def cleanup_jobs(
        self,
        *,
        older_than_hours: int | None = None,
        statuses: list[ForecastJobTerminalStatus] | None = None,
    ) -> ForecastJobCleanupResponse:
        retention_hours = older_than_hours or self.default_retention_hours
        cleanup_statuses = set(statuses or sorted(TERMINAL_JOB_STATUSES))
        cutoff = datetime.now(UTC) - timedelta(hours=retention_hours)
        deleted_count = await self.store.delete_older_than(
            cutoff=cutoff,
            statuses=cleanup_statuses,
        )
        return ForecastJobCleanupResponse(
            deleted_count=deleted_count,
            cutoff=cutoff,
            statuses=sorted(cleanup_statuses),
        )

    async def run_job(self, job_id: str) -> None:
        job = await self.store.get(job_id)
        if job.status != "queued":
            return

        now = datetime.now(UTC)
        running_job = append_job_event(
            job.model_copy(
                update={
                    "status": "running",
                    "started_at": now,
                    "diagnostics": ForecastJobDiagnostics(
                        provider=None,
                        message="Forecast provider request is running.",
                    ),
                    "error": None,
                }
            ),
            status="running",
            message="Forecast provider request started.",
            occurred_at=now,
        )
        try:
            await self.store.update_if_status(running_job, expected_statuses={"queued"})
        except ForecastJobTransitionError:
            return

        try:
            provider_result = await self._get_provider_result(job)
        except ForecastProviderUnavailableError as error:
            await self._mark_failed(job_id=job_id, error=str(error))
        except Exception as error:  # pragma: no cover - defensive boundary
            await self._mark_failed(job_id=job_id, error=f"Unexpected forecast job error: {error}")
        else:
            completed = datetime.now(UTC)
            current = await self.store.get(job_id)
            if current.status != "running":
                return

            succeeded = append_job_event(
                current.model_copy(
                    update={
                        "status": "succeeded",
                        "completed_at": completed,
                        "forecast": provider_result.summary,
                        "diagnostics": ForecastJobDiagnostics(
                            **{
                                **provider_result.diagnostics,
                                "message": "Forecast summary is ready.",
                            }
                        ),
                        "error": None,
                    }
                ),
                status="succeeded",
                message="Forecast summary is ready.",
                occurred_at=completed,
            )
            try:
                await self.store.update_if_status(succeeded, expected_statuses={"running"})
            except ForecastJobTransitionError:
                return

    async def _get_provider_result(self, job: ForecastJob) -> ForecastProviderResult:
        diagnostic_method = getattr(self.provider, "get_point_forecast_with_diagnostics", None)
        if diagnostic_method is not None:
            return await diagnostic_method(latitude=job.latitude, longitude=job.longitude)

        summary = await self.provider.get_point_forecast(
            latitude=job.latitude,
            longitude=job.longitude,
        )
        return ForecastProviderResult(
            summary=summary,
            diagnostics={
                "provider": summary.provider,
                "message": "Provider did not return extended job diagnostics.",
            },
        )

    async def _mark_failed(self, *, job_id: str, error: str) -> None:
        job = await self.store.get(job_id)
        if job.status != "running":
            return

        failed_at = datetime.now(UTC)
        failed = append_job_event(
            job.model_copy(
                update={
                    "status": "failed",
                    "completed_at": failed_at,
                    "error": error,
                    "diagnostics": ForecastJobDiagnostics(message="Forecast job failed."),
                }
            ),
            status="failed",
            message="Forecast job failed.",
            occurred_at=failed_at,
        )
        try:
            await self.store.update_if_status(failed, expected_statuses={"running"})
        except ForecastJobTransitionError:
            return
