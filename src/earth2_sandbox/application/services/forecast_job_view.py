from __future__ import annotations

from datetime import datetime

from earth2_sandbox.domain.jobs.events import record_forecast_job_event
from earth2_sandbox.domain.jobs.status import TERMINAL_JOB_STATUSES, ForecastJobStatus
from earth2_sandbox.schemas.jobs import (
    ForecastJob,
    ForecastJobEvent,
    ForecastJobPollResponse,
    ForecastJobSummary,
)


def with_job_links(job: ForecastJob) -> ForecastJob:
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


def append_job_event(
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


def to_job_summary(job: ForecastJob) -> ForecastJobSummary:
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


def to_job_poll_response(job: ForecastJob) -> ForecastJobPollResponse:
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
