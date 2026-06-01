from __future__ import annotations

from collections.abc import Collection
from datetime import datetime, timedelta

from earth2_sandbox.domain.jobs.status import ForecastJobStatus, ForecastJobTerminalStatus


def can_transition_from(
    *,
    current_status: ForecastJobStatus,
    expected_statuses: Collection[ForecastJobStatus],
) -> bool:
    return current_status in expected_statuses


def should_mark_job_stale(
    *,
    updated_at: datetime,
    now: datetime,
    timeout_seconds: int,
) -> bool:
    return updated_at <= now - timedelta(seconds=timeout_seconds)


def should_cleanup_job(
    *,
    status: ForecastJobStatus,
    completed_at: datetime | None,
    updated_at: datetime,
    cutoff: datetime,
    statuses: Collection[ForecastJobTerminalStatus],
) -> bool:
    if status not in statuses:
        return False
    reference_time = completed_at or updated_at
    return reference_time < cutoff
