"""Forecast job domain vocabulary and lifecycle policies."""

from earth2_sandbox.domain.jobs.entities import (
    ForecastJobAttempt,
    ForecastJobCoordinates,
    ForecastJobIdentity,
    InvalidForecastJobAttemptError,
    InvalidForecastJobCoordinatesError,
    InvalidForecastJobIdentityError,
)
from earth2_sandbox.domain.jobs.events import ForecastJobEventRecord, record_forecast_job_event
from earth2_sandbox.domain.jobs.policies import (
    can_transition_from,
    should_cleanup_job,
    should_mark_job_stale,
)
from earth2_sandbox.domain.jobs.priority import (
    DEFAULT_FORECAST_JOB_PRIORITY,
    FORECAST_JOB_PRIORITY_RANK,
    ForecastJobPriority,
    priority_rank,
)
from earth2_sandbox.domain.jobs.status import (
    ACTIVE_JOB_STATUSES,
    ALL_JOB_STATUSES,
    TERMINAL_JOB_STATUSES,
    ForecastJobStatus,
    ForecastJobTerminalStatus,
    is_active_job_status,
    is_terminal_job_status,
)

__all__ = [
    "ACTIVE_JOB_STATUSES",
    "ALL_JOB_STATUSES",
    "DEFAULT_FORECAST_JOB_PRIORITY",
    "FORECAST_JOB_PRIORITY_RANK",
    "TERMINAL_JOB_STATUSES",
    "ForecastJobAttempt",
    "ForecastJobCoordinates",
    "ForecastJobEventRecord",
    "ForecastJobIdentity",
    "ForecastJobPriority",
    "ForecastJobStatus",
    "ForecastJobTerminalStatus",
    "InvalidForecastJobAttemptError",
    "InvalidForecastJobCoordinatesError",
    "InvalidForecastJobIdentityError",
    "can_transition_from",
    "is_active_job_status",
    "is_terminal_job_status",
    "priority_rank",
    "record_forecast_job_event",
    "should_cleanup_job",
    "should_mark_job_stale",
]
