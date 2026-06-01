"""Forecast job domain vocabulary and lifecycle policies."""

from earth2_sandbox.domain.jobs.events import ForecastJobEventRecord, record_forecast_job_event
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
    is_active_job_status,
    is_terminal_job_status,
)

__all__ = [
    "ACTIVE_JOB_STATUSES",
    "ALL_JOB_STATUSES",
    "TERMINAL_JOB_STATUSES",
    "ForecastJobEventRecord",
    "ForecastJobStatus",
    "ForecastJobTerminalStatus",
    "can_transition_from",
    "is_active_job_status",
    "is_terminal_job_status",
    "record_forecast_job_event",
    "should_cleanup_job",
    "should_mark_job_stale",
]
