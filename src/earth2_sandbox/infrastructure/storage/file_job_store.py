from __future__ import annotations

import asyncio
from collections.abc import Collection
from datetime import datetime
from pathlib import Path

from earth2_sandbox.application.errors import ForecastJobNotFoundError
from earth2_sandbox.application.ports.clock import Clock
from earth2_sandbox.application.ports.id_generator import IdGenerator
from earth2_sandbox.domain.jobs.policies import should_cleanup_job
from earth2_sandbox.domain.jobs.status import (
    ACTIVE_JOB_STATUSES,
    ALL_JOB_STATUSES,
    ForecastJobStatus,
    ForecastJobTerminalStatus,
)
from earth2_sandbox.infrastructure.runtime import SystemClock, UuidIdGenerator
from earth2_sandbox.infrastructure.storage.job_store_helpers import (
    build_new_job,
    ensure_transition_allowed,
    normalize_job_id,
    prepare_job_for_update,
    sort_and_filter_jobs,
    sort_jobs,
)
from earth2_sandbox.schemas.jobs import ForecastJob


class FileForecastJobStore:
    """Filesystem-backed job store for local hosted-result observation.

    Jobs are stored as one JSON file per job id. This is intentionally simple:
    it preserves diagnostics across backend restarts without introducing Redis
    or a database before the job contract settles.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        clock: Clock | None = None,
        id_generator: IdGenerator | None = None,
    ) -> None:
        self.root = Path(root)
        self._lock = asyncio.Lock()
        self._clock = clock or SystemClock()
        self._id_generator = id_generator or UuidIdGenerator()

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
            clock=self._clock,
            id_generator=self._id_generator,
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
        next_job = prepare_job_for_update(job, clock=self._clock)
        async with self._lock:
            path = self._path(next_job.id)
            if not path.exists():
                raise ForecastJobNotFoundError(next_job.id)
            current = ForecastJob.model_validate_json(path.read_text(encoding="utf-8"))
            ensure_transition_allowed(current=current, expected_statuses=expected_statuses)
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
        return sort_and_filter_jobs(jobs=jobs, limit=limit, status=status)

    async def list_active(self) -> list[ForecastJob]:
        async with self._lock:
            jobs = self._read_all_unlocked()
        return sort_jobs([job for job in jobs if job.status in ACTIVE_JOB_STATUSES])

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
        normalized_job_id = normalize_job_id(job_id)
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
