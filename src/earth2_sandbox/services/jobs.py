from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import uuid4

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
    ForecastJobStatus,
    ForecastJobSummary,
    ForecastJobTerminalStatus,
)


class ForecastJobNotFoundError(KeyError):
    """Raised when a forecast job id is unknown to the configured job store."""


class ForecastJobConflictError(RuntimeError):
    """Raised when a job state transition is not valid for the current status."""


TERMINAL_JOB_STATUSES: set[ForecastJobTerminalStatus] = {
    "succeeded",
    "failed",
    "cancelled",
}


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

    async def list_recent(
        self,
        *,
        limit: int,
        status: ForecastJobStatus | None = None,
    ) -> list[ForecastJob]: ...

    async def delete_older_than(
        self,
        *,
        cutoff: datetime,
        statuses: set[ForecastJobTerminalStatus],
    ) -> int: ...


class DiagnosticForecastProvider(Protocol):
    async def get_point_forecast_with_diagnostics(
        self,
        latitude: float,
        longitude: float,
    ) -> ForecastProviderResult: ...


class InMemoryForecastJobStore:
    """Small process-local job store.

    This is the VIP boundary for the queued job contract. It is intentionally
    replaceable by Redis, a database, or a real task queue once the contract is
    stable.
    """

    def __init__(self) -> None:
        self._jobs: dict[str, ForecastJob] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        *,
        latitude: float,
        longitude: float,
        parent_job_id: str | None = None,
        attempt: int = 1,
    ) -> ForecastJob:
        job = _build_new_job(
            latitude=latitude,
            longitude=longitude,
            parent_job_id=parent_job_id,
            attempt=attempt,
        )
        async with self._lock:
            self._jobs[job.id] = job
        return job

    async def get(self, job_id: str) -> ForecastJob:
        async with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise ForecastJobNotFoundError(job_id)
        return job

    async def update(self, job: ForecastJob) -> ForecastJob:
        next_job = job.model_copy(update={"updated_at": datetime.now(UTC)})
        async with self._lock:
            if next_job.id not in self._jobs:
                raise ForecastJobNotFoundError(next_job.id)
            self._jobs[next_job.id] = next_job
        return next_job

    async def list_recent(
        self,
        *,
        limit: int,
        status: ForecastJobStatus | None = None,
    ) -> list[ForecastJob]:
        async with self._lock:
            jobs = list(self._jobs.values())
        return _sort_and_filter_jobs(jobs=jobs, limit=limit, status=status)

    async def delete_older_than(
        self,
        *,
        cutoff: datetime,
        statuses: set[ForecastJobTerminalStatus],
    ) -> int:
        async with self._lock:
            job_ids = [
                job.id
                for job in self._jobs.values()
                if _is_cleanup_candidate(job=job, cutoff=cutoff, statuses=statuses)
            ]
            for job_id in job_ids:
                del self._jobs[job_id]
        return len(job_ids)


class FileForecastJobStore:
    """Filesystem-backed job store for local hosted-result observation.

    Jobs are stored as one JSON file per job id. This is intentionally simple:
    it preserves diagnostics across backend restarts without introducing Redis
    or a database before the job contract settles.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._lock = asyncio.Lock()

    async def create(
        self,
        *,
        latitude: float,
        longitude: float,
        parent_job_id: str | None = None,
        attempt: int = 1,
    ) -> ForecastJob:
        job = _build_new_job(
            latitude=latitude,
            longitude=longitude,
            parent_job_id=parent_job_id,
            attempt=attempt,
        )
        async with self._lock:
            self._write(job)
        return job

    async def get(self, job_id: str) -> ForecastJob:
        async with self._lock:
            path = self._path(job_id)
            if not path.exists():
                raise ForecastJobNotFoundError(job_id)
            return ForecastJob.model_validate_json(path.read_text(encoding="utf-8"))

    async def update(self, job: ForecastJob) -> ForecastJob:
        next_job = job.model_copy(update={"updated_at": datetime.now(UTC)})
        async with self._lock:
            if not self._path(next_job.id).exists():
                raise ForecastJobNotFoundError(next_job.id)
            self._write(next_job)
        return next_job

    async def list_recent(
        self,
        *,
        limit: int,
        status: ForecastJobStatus | None = None,
    ) -> list[ForecastJob]:
        async with self._lock:
            jobs: list[ForecastJob] = []
            if self.root.exists():
                for path in self.root.glob("*.json"):
                    try:
                        jobs.append(ForecastJob.model_validate_json(path.read_text("utf-8")))
                    except ValueError:
                        continue
        return _sort_and_filter_jobs(jobs=jobs, limit=limit, status=status)

    async def delete_older_than(
        self,
        *,
        cutoff: datetime,
        statuses: set[ForecastJobTerminalStatus],
    ) -> int:
        deleted_count = 0
        async with self._lock:
            if not self.root.exists():
                return 0

            for path in self.root.glob("*.json"):
                try:
                    job = ForecastJob.model_validate_json(path.read_text("utf-8"))
                except ValueError:
                    continue

                if not _is_cleanup_candidate(job=job, cutoff=cutoff, statuses=statuses):
                    continue

                path.unlink()
                deleted_count += 1
        return deleted_count

    def _path(self, job_id: str) -> Path:
        return self.root / f"{job_id}.json"

    def _write(self, job: ForecastJob) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self._path(job.id)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            job.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)


class ForecastJobService:
    def __init__(
        self,
        *,
        provider: ForecastProvider,
        store: ForecastJobStore | None = None,
        default_retention_hours: int = 168,
    ) -> None:
        self.provider = provider
        self.store = store or InMemoryForecastJobStore()
        self.default_retention_hours = default_retention_hours

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
        return self._with_links(await self.store.update(cancelled))

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
        await self.store.update(running_job)

        try:
            provider_result = await self._get_provider_result(job)
        except ForecastProviderUnavailableError as error:
            await self._mark_failed(job_id=job_id, error=str(error))
        except Exception as error:  # pragma: no cover - defensive boundary
            await self._mark_failed(job_id=job_id, error=f"Unexpected forecast job error: {error}")
        else:
            completed = datetime.now(UTC)
            current = await self.store.get(job_id)
            if current.status == "cancelled":
                return

            await self.store.update(
                self._append_event(
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
            )

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
        if job.status == "cancelled":
            return

        failed_at = datetime.now(UTC)
        await self.store.update(
            self._append_event(
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
        )

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
        return job.model_copy(
            update={
                "events": [
                    *job.events,
                    ForecastJobEvent(
                        occurred_at=occurred_at or datetime.now(UTC),
                        status=status,
                        message=message,
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


def _sort_and_filter_jobs(
    *,
    jobs: list[ForecastJob],
    limit: int,
    status: ForecastJobStatus | None,
) -> list[ForecastJob]:
    filtered = [job for job in jobs if status is None or job.status == status]
    filtered.sort(key=lambda job: (job.created_at, job.id), reverse=True)
    return filtered[:limit]


def _build_new_job(
    *,
    latitude: float,
    longitude: float,
    parent_job_id: str | None,
    attempt: int,
) -> ForecastJob:
    now = datetime.now(UTC)
    message = "Forecast retry accepted." if parent_job_id else "Forecast job accepted."
    return ForecastJob(
        id=str(uuid4()),
        status="queued",
        latitude=latitude,
        longitude=longitude,
        parent_job_id=parent_job_id,
        attempt=attempt,
        created_at=now,
        updated_at=now,
        diagnostics=ForecastJobDiagnostics(message="Waiting for forecast worker."),
        events=[
            ForecastJobEvent(
                occurred_at=now,
                status="queued",
                message=message,
            )
        ],
    )


def _is_cleanup_candidate(
    *,
    job: ForecastJob,
    cutoff: datetime,
    statuses: set[ForecastJobTerminalStatus],
) -> bool:
    if job.status not in statuses:
        return False
    reference_time = job.completed_at or job.updated_at
    return reference_time < cutoff
