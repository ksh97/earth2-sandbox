from __future__ import annotations

import asyncio
from collections.abc import Collection
from datetime import datetime

from earth2_sandbox.application.errors import ForecastJobNotFoundError
from earth2_sandbox.domain.jobs.policies import should_cleanup_job
from earth2_sandbox.domain.jobs.status import (
    ACTIVE_JOB_STATUSES,
    ALL_JOB_STATUSES,
    ForecastJobStatus,
    ForecastJobTerminalStatus,
)
from earth2_sandbox.infrastructure.storage.job_store_helpers import (
    build_new_job,
    ensure_transition_allowed,
    normalize_job_id,
    prepare_job_for_update,
    sort_and_filter_jobs,
    sort_jobs,
)
from earth2_sandbox.schemas.jobs import ForecastJob


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
        job = build_new_job(
            latitude=latitude,
            longitude=longitude,
            parent_job_id=parent_job_id,
            attempt=attempt,
        )
        async with self._lock:
            self._jobs[job.id] = job
        return job

    async def get(self, job_id: str) -> ForecastJob:
        normalized_job_id = normalize_job_id(job_id)
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
        next_job = prepare_job_for_update(job)
        async with self._lock:
            current = self._jobs.get(next_job.id)
            if current is None:
                raise ForecastJobNotFoundError(next_job.id)
            ensure_transition_allowed(current=current, expected_statuses=expected_statuses)
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
        return sort_and_filter_jobs(jobs=jobs, limit=limit, status=status)

    async def list_active(self) -> list[ForecastJob]:
        async with self._lock:
            jobs = list(self._jobs.values())
        return sort_jobs([job for job in jobs if job.status in ACTIVE_JOB_STATUSES])

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
