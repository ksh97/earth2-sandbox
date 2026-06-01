from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from earth2_sandbox.application.errors import (
    ForecastJobConflictError,
    ForecastJobNotFoundError,
    ForecastJobTransitionError,
)
from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.domain.jobs.events import record_forecast_job_event
from earth2_sandbox.domain.jobs.policies import should_mark_job_stale
from earth2_sandbox.domain.jobs.status import (
    ACTIVE_JOB_STATUSES,
    TERMINAL_JOB_STATUSES,
    ForecastJobStatus,
    ForecastJobTerminalStatus,
)
from earth2_sandbox.infrastructure.storage import (
    FileForecastJobStore,
    InMemoryForecastJobStore,
)
from earth2_sandbox.providers import (
    ForecastProvider,
    ForecastProviderResult,
    ForecastProviderUnavailableError,
)
from earth2_sandbox.schemas.jobs import (
    ForecastJob,
    ForecastJobCleanupResponse,
    ForecastJobDiagnostics,
    ForecastJobEvent,
    ForecastJobListResponse,
    ForecastJobPollResponse,
    ForecastJobSummary,
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


@dataclass(frozen=True)
class ForecastJobRecoveryReport:
    scanned_count: int
    requeued_count: int
    timed_out_count: int
    skipped_count: int


class DiagnosticForecastProvider(Protocol):
    async def get_point_forecast_with_diagnostics(
        self,
        latitude: float,
        longitude: float,
    ) -> ForecastProviderResult: ...


class ForecastJobService:
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

    async def create_job(self, *, latitude: float, longitude: float) -> ForecastJob:
        return self._with_links(await self.store.create(latitude=latitude, longitude=longitude))

    async def get_job(self, job_id: str) -> ForecastJob:
        return self._with_links(await self.store.get(job_id))

    async def list_recent_jobs(
        self,
        *,
        limit: int,
        status: ForecastJobStatus | None = None,
    ) -> ForecastJobListResponse:
        jobs = await self.store.list_recent(limit=limit, status=status)
        summaries = [self._to_summary(self._with_links(job)) for job in jobs]
        return ForecastJobListResponse(count=len(summaries), jobs=summaries)

    async def poll_job(self, job_id: str) -> ForecastJobPollResponse:
        return self._to_poll_response(self._with_links(await self.store.get(job_id)))

    async def cancel_job(self, job_id: str) -> ForecastJob:
        job = await self.store.get(job_id)
        if job.status in TERMINAL_JOB_STATUSES:
            raise ForecastJobConflictError(f"Cannot cancel a {job.status} forecast job.")

        now = datetime.now(UTC)
        cancelled = self._append_event(
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
            return self._with_links(
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
        return self._with_links(retry)

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

    async def recover_interrupted_jobs(
        self,
        *,
        worker: ForecastJobWorker,
        stale_timeout_seconds: int | None = None,
    ) -> ForecastJobRecoveryReport:
        timeout = stale_timeout_seconds or self.default_stale_timeout_seconds
        now = datetime.now(UTC)
        active_jobs = await self.store.list_active()
        requeued_count = 0
        timed_out_count = 0
        skipped_count = 0

        for job in active_jobs:
            if should_mark_job_stale(
                updated_at=job.updated_at,
                now=now,
                timeout_seconds=timeout,
            ):
                if await self._mark_timed_out(job=job, occurred_at=now, timeout_seconds=timeout):
                    timed_out_count += 1
                else:
                    skipped_count += 1
                continue

            if job.status == "running":
                recovered = self._append_event(
                    job.model_copy(
                        update={
                            "status": "queued",
                            "started_at": None,
                            "diagnostics": ForecastJobDiagnostics(
                                provider=job.diagnostics.provider if job.diagnostics else None,
                                message="Forecast job recovered for worker retry.",
                            ),
                            "error": None,
                        }
                    ),
                    status="queued",
                    message="Forecast job recovered for worker retry.",
                    occurred_at=now,
                )
                try:
                    job = await self.store.update_if_status(
                        recovered,
                        expected_statuses={"running"},
                    )
                except ForecastJobTransitionError:
                    skipped_count += 1
                    continue

            worker.enqueue(job.id)
            requeued_count += 1

        return ForecastJobRecoveryReport(
            scanned_count=len(active_jobs),
            requeued_count=requeued_count,
            timed_out_count=timed_out_count,
            skipped_count=skipped_count,
        )

    async def run_job(self, job_id: str) -> None:
        job = await self.store.get(job_id)
        if job.status != "queued":
            return

        now = datetime.now(UTC)
        running_job = self._append_event(
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

            succeeded = self._append_event(
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
        failed = self._append_event(
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

    async def _mark_timed_out(
        self,
        *,
        job: ForecastJob,
        occurred_at: datetime,
        timeout_seconds: int,
    ) -> bool:
        timeout_message = (
            f"Forecast worker timed out after {timeout_seconds} seconds without progress."
        )
        timed_out = self._append_event(
            job.model_copy(
                update={
                    "status": "failed",
                    "completed_at": occurred_at,
                    "error": timeout_message,
                    "diagnostics": ForecastJobDiagnostics(
                        provider=job.diagnostics.provider if job.diagnostics else None,
                        message="Forecast worker timed out.",
                    ),
                }
            ),
            status="failed",
            message="Forecast worker timed out.",
            occurred_at=occurred_at,
        )
        try:
            await self.store.update_if_status(
                timed_out,
                expected_statuses=ACTIVE_JOB_STATUSES,
            )
        except ForecastJobTransitionError:
            return False
        return True

    def _with_links(self, job: ForecastJob) -> ForecastJob:
        return job.model_copy(
            update={
                "links": {
                    "self": f"/api/v1/forecast/jobs/{job.id}",
                    "poll": f"/api/v1/forecast/jobs/{job.id}/poll",
                    "point_forecast": (
                        "/api/v1/forecast/point"
                        f"?latitude={job.latitude}&longitude={job.longitude}"
                    ),
                    "retry": f"/api/v1/forecast/jobs/{job.id}/retry",
                    "cancel": f"/api/v1/forecast/jobs/{job.id}/cancel",
                }
            }
        )

    def _append_event(
        self,
        job: ForecastJob,
        *,
        status: ForecastJobStatus,
        message: str,
        occurred_at: datetime | None = None,
    ) -> ForecastJob:
        event = record_forecast_job_event(
            status=status,
            message=message,
            occurred_at=occurred_at,
        )
        return job.model_copy(
            update={
                "events": [
                    *job.events,
                    ForecastJobEvent(
                        occurred_at=event.occurred_at,
                        status=event.status,
                        message=event.message,
                    ),
                ]
            }
        )

    def _to_summary(self, job: ForecastJob) -> ForecastJobSummary:
        return ForecastJobSummary(
            id=job.id,
            status=job.status,
            latitude=job.latitude,
            longitude=job.longitude,
            parent_job_id=job.parent_job_id,
            attempt=job.attempt,
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            diagnostics=job.diagnostics,
            error=job.error,
            links=job.links,
        )

    def _to_poll_response(self, job: ForecastJob) -> ForecastJobPollResponse:
        terminal = job.status in TERMINAL_JOB_STATUSES
        return ForecastJobPollResponse(
            id=job.id,
            status=job.status,
            terminal=terminal,
            forecast_ready=job.forecast is not None,
            updated_at=job.updated_at,
            retry_after_seconds=None if terminal else 2,
            event_count=len(job.events),
            latest_event=job.events[-1] if job.events else None,
            links=job.links,
        )
