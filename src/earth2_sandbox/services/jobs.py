from __future__ import annotations

import asyncio
from datetime import UTC, datetime
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
    ForecastJobDiagnostics,
    ForecastJobEvent,
    ForecastJobListResponse,
    ForecastJobStatus,
    ForecastJobSummary,
)


class ForecastJobNotFoundError(KeyError):
    """Raised when a forecast job id is unknown to the configured job store."""


class ForecastJobStore(Protocol):
    async def create(self, *, latitude: float, longitude: float) -> ForecastJob: ...

    async def get(self, job_id: str) -> ForecastJob: ...

    async def update(self, job: ForecastJob) -> ForecastJob: ...

    async def list_recent(
        self,
        *,
        limit: int,
        status: ForecastJobStatus | None = None,
    ) -> list[ForecastJob]: ...


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

    async def create(self, *, latitude: float, longitude: float) -> ForecastJob:
        now = datetime.now(UTC)
        job = ForecastJob(
            id=str(uuid4()),
            status="queued",
            latitude=latitude,
            longitude=longitude,
            created_at=now,
            updated_at=now,
            diagnostics=ForecastJobDiagnostics(message="Waiting for forecast worker."),
            events=[
                ForecastJobEvent(
                    occurred_at=now,
                    status="queued",
                    message="Forecast job accepted.",
                )
            ],
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


class FileForecastJobStore:
    """Filesystem-backed job store for local hosted-result observation.

    Jobs are stored as one JSON file per job id. This is intentionally simple:
    it preserves diagnostics across backend restarts without introducing Redis
    or a database before the job contract settles.
    """

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self._lock = asyncio.Lock()

    async def create(self, *, latitude: float, longitude: float) -> ForecastJob:
        now = datetime.now(UTC)
        job = ForecastJob(
            id=str(uuid4()),
            status="queued",
            latitude=latitude,
            longitude=longitude,
            created_at=now,
            updated_at=now,
            diagnostics=ForecastJobDiagnostics(message="Waiting for forecast worker."),
            events=[
                ForecastJobEvent(
                    occurred_at=now,
                    status="queued",
                    message="Forecast job accepted.",
                )
            ],
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
    ) -> None:
        self.provider = provider
        self.store = store or InMemoryForecastJobStore()

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

    async def run_job(self, job_id: str) -> None:
        job = await self.store.get(job_id)
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
        await self.store.update(
            self._append_event(
                job.model_copy(
                    update={
                        "status": "failed",
                        "completed_at": datetime.now(UTC),
                        "error": error,
                        "diagnostics": ForecastJobDiagnostics(message="Forecast job failed."),
                    }
                ),
                status="failed",
                message="Forecast job failed.",
            )
        )

    def _with_links(self, job: ForecastJob) -> ForecastJob:
        return job.model_copy(
            update={
                "links": {
                    "self": f"/api/v1/forecast/jobs/{job.id}",
                    "point_forecast": (
                        "/api/v1/forecast/point"
                        f"?latitude={job.latitude}&longitude={job.longitude}"
                    ),
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
            created_at=job.created_at,
            updated_at=job.updated_at,
            completed_at=job.completed_at,
            diagnostics=job.diagnostics,
            error=job.error,
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
