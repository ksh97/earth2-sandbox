from __future__ import annotations

import asyncio
from collections.abc import Collection
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from earth2_sandbox.domain.jobs.events import record_forecast_job_event
from earth2_sandbox.domain.jobs.policies import (
    can_transition_from,
    should_cleanup_job,
    should_mark_job_stale,
)
from earth2_sandbox.domain.jobs.status import (
    ACTIVE_JOB_STATUSES,
    ALL_JOB_STATUSES,
    TERMINAL_JOB_STATUSES,
    ForecastJobStatus,
    ForecastJobTerminalStatus,
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


class ForecastJobNotFoundError(KeyError):
    """Raised when a forecast job id is unknown to the configured job store."""


class ForecastJobConflictError(RuntimeError):
    """Raised when a job state transition is not valid for the current status."""


class ForecastJobTransitionError(ForecastJobConflictError):
    """Raised when a conditional job update observes a different current status."""

    def __init__(
        self,
        *,
        job_id: str,
        current_status: ForecastJobStatus,
        expected_statuses: Collection[ForecastJobStatus],
    ) -> None:
        self.job_id = job_id
        self.current_status = current_status
        self.expected_statuses = frozenset(expected_statuses)
        expected = ", ".join(sorted(self.expected_statuses))
        super().__init__(
            f"Cannot transition forecast job {job_id} from {current_status}; "
            f"expected one of: {expected}."
        )


@dataclass(frozen=True)
class ForecastJobRecoveryReport:
    scanned_count: int
    requeued_count: int
    timed_out_count: int
    skipped_count: int


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
        normalized_job_id = _normalize_job_id(job_id)
        async with self._lock:
            job = self._jobs.get(normalized_job_id)
        if job is None:
            raise ForecastJobNotFoundError(job_id)
        return job

    async def update(self, job: ForecastJob) -> ForecastJob:
        return await self.update_if_status(job, expected_statuses=ALL_JOB_STATUSES)

    async def update_if_status(
        self,
        job: ForecastJob,
        *,
        expected_statuses: Collection[ForecastJobStatus],
    ) -> ForecastJob:
        next_job = _prepare_job_for_update(job)
        async with self._lock:
            current = self._jobs.get(next_job.id)
            if current is None:
                raise ForecastJobNotFoundError(next_job.id)
            _ensure_transition_allowed(current=current, expected_statuses=expected_statuses)
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

    async def list_active(self) -> list[ForecastJob]:
        async with self._lock:
            jobs = list(self._jobs.values())
        return _sort_jobs([job for job in jobs if job.status in ACTIVE_JOB_STATUSES])

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
                if should_cleanup_job(
                    status=job.status,
                    completed_at=job.completed_at,
                    updated_at=job.updated_at,
                    cutoff=cutoff,
                    statuses=statuses,
                )
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
        return await self.update_if_status(job, expected_statuses=ALL_JOB_STATUSES)

    async def update_if_status(
        self,
        job: ForecastJob,
        *,
        expected_statuses: Collection[ForecastJobStatus],
    ) -> ForecastJob:
        next_job = _prepare_job_for_update(job)
        async with self._lock:
            path = self._path(next_job.id)
            if not path.exists():
                raise ForecastJobNotFoundError(next_job.id)
            current = ForecastJob.model_validate_json(path.read_text(encoding="utf-8"))
            _ensure_transition_allowed(current=current, expected_statuses=expected_statuses)
            self._write(next_job)
        return next_job

    async def list_recent(
        self,
        *,
        limit: int,
        status: ForecastJobStatus | None = None,
    ) -> list[ForecastJob]:
        async with self._lock:
            jobs = self._read_all_unlocked()
        return _sort_and_filter_jobs(jobs=jobs, limit=limit, status=status)

    async def list_active(self) -> list[ForecastJob]:
        async with self._lock:
            jobs = self._read_all_unlocked()
        return _sort_jobs([job for job in jobs if job.status in ACTIVE_JOB_STATUSES])

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

                if not should_cleanup_job(
                    status=job.status,
                    completed_at=job.completed_at,
                    updated_at=job.updated_at,
                    cutoff=cutoff,
                    statuses=statuses,
                ):
                    continue

                path.unlink()
                deleted_count += 1
        return deleted_count

    def _path(self, job_id: str) -> Path:
        normalized_job_id = _normalize_job_id(job_id)
        root = self.root.resolve()
        target = (root / f"{normalized_job_id}.json").resolve()
        try:
            target.relative_to(root)
        except ValueError as error:
            raise ForecastJobNotFoundError(job_id) from error
        return target

    def _write(self, job: ForecastJob) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        target = self._path(job.id)
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(
            job.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temporary.replace(target)

    def _read_all_unlocked(self) -> list[ForecastJob]:
        if not self.root.exists():
            return []

        jobs: list[ForecastJob] = []
        for path in self.root.glob("*.json"):
            try:
                jobs.append(ForecastJob.model_validate_json(path.read_text("utf-8")))
            except ValueError:
                continue
        return jobs


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


def _sort_and_filter_jobs(
    *,
    jobs: list[ForecastJob],
    limit: int,
    status: ForecastJobStatus | None,
) -> list[ForecastJob]:
    filtered = [job for job in jobs if status is None or job.status == status]
    return _sort_jobs(filtered)[:limit]


def _sort_jobs(jobs: list[ForecastJob]) -> list[ForecastJob]:
    return sorted(jobs, key=lambda job: (job.created_at, job.id), reverse=True)


def _normalize_job_id(job_id: str) -> str:
    try:
        parsed = UUID(job_id)
    except (TypeError, ValueError) as error:
        raise ForecastJobNotFoundError(job_id) from error

    return str(parsed)


def _prepare_job_for_update(job: ForecastJob) -> ForecastJob:
    normalized_job_id = _normalize_job_id(job.id)
    return job.model_copy(update={"id": normalized_job_id, "updated_at": datetime.now(UTC)})


def _ensure_transition_allowed(
    *,
    current: ForecastJob,
    expected_statuses: Collection[ForecastJobStatus],
) -> None:
    if not can_transition_from(
        current_status=current.status,
        expected_statuses=expected_statuses,
    ):
        raise ForecastJobTransitionError(
            job_id=current.id,
            current_status=current.status,
            expected_statuses=expected_statuses,
        )


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
