from __future__ import annotations

from datetime import UTC, datetime

from earth2_sandbox.application.errors import ForecastJobConflictError, ForecastJobTransitionError
from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.services.forecast_job_view import append_job_event, with_job_links
from earth2_sandbox.domain.jobs.status import ACTIVE_JOB_STATUSES, TERMINAL_JOB_STATUSES
from earth2_sandbox.schemas.jobs import ForecastJob, ForecastJobDiagnostics


class CancelForecastJob:
    def __init__(self, *, store: ForecastJobStore) -> None:
        self.store = store

    async def execute(self, job_id: str) -> ForecastJob:
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
