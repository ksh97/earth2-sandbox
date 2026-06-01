from __future__ import annotations

from collections.abc import Collection
from datetime import UTC, datetime
from uuid import UUID, uuid4

from earth2_sandbox.application.errors import ForecastJobNotFoundError, ForecastJobTransitionError
from earth2_sandbox.domain.jobs.policies import can_transition_from
from earth2_sandbox.domain.jobs.status import ForecastJobStatus
from earth2_sandbox.schemas.jobs import ForecastJob, ForecastJobDiagnostics, ForecastJobEvent


def build_new_job(
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


def normalize_job_id(job_id: str) -> str:
    try:
        parsed = UUID(job_id)
    except (TypeError, ValueError) as error:
        raise ForecastJobNotFoundError(job_id) from error

    return str(parsed)


def prepare_job_for_update(job: ForecastJob) -> ForecastJob:
    normalized_job_id = normalize_job_id(job.id)
    return job.model_copy(update={"id": normalized_job_id, "updated_at": datetime.now(UTC)})


def ensure_transition_allowed(
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


def sort_and_filter_jobs(
    *,
    jobs: list[ForecastJob],
    limit: int,
    status: ForecastJobStatus | None,
) -> list[ForecastJob]:
    filtered = [job for job in jobs if status is None or job.status == status]
    return sort_jobs(filtered)[:limit]


def sort_jobs(jobs: list[ForecastJob]) -> list[ForecastJob]:
    return sorted(jobs, key=lambda job: (job.created_at, job.id), reverse=True)
