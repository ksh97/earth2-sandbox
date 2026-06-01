from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from earth2_sandbox.application.errors import ForecastJobTransitionError
from earth2_sandbox.application.ports.clock import Clock
from earth2_sandbox.application.ports.forecast_job_store import ForecastJobStore
from earth2_sandbox.application.ports.forecast_job_worker import ForecastJobWorker
from earth2_sandbox.application.services.forecast_job_view import append_job_event
from earth2_sandbox.domain.jobs.policies import should_mark_job_stale
from earth2_sandbox.domain.jobs.status import ACTIVE_JOB_STATUSES
from earth2_sandbox.schemas.jobs import ForecastJob, ForecastJobDiagnostics


@dataclass(frozen=True)
class ForecastJobRecoveryReport:
    scanned_count: int
    requeued_count: int
    timed_out_count: int
    skipped_count: int


class ForecastJobRecoveryService:
    def __init__(
        self,
        *,
        store: ForecastJobStore,
        clock: Clock,
        default_stale_timeout_seconds: int = 1800,
    ) -> None:
        self.store = store
        self.clock = clock
        self.default_stale_timeout_seconds = default_stale_timeout_seconds

    async def recover_interrupted_jobs(
        self,
        *,
        worker: ForecastJobWorker,
        stale_timeout_seconds: int | None = None,
    ) -> ForecastJobRecoveryReport:
        timeout = stale_timeout_seconds or self.default_stale_timeout_seconds
        now = self.clock.now()
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
                recovered = append_job_event(
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
        timed_out = append_job_event(
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
