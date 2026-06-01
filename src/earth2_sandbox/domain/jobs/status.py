from __future__ import annotations

from typing import Literal, TypeAlias

ForecastJobStatus: TypeAlias = Literal["queued", "running", "succeeded", "failed", "cancelled"]
ForecastJobTerminalStatus: TypeAlias = Literal["succeeded", "failed", "cancelled"]

TERMINAL_JOB_STATUSES: frozenset[ForecastJobTerminalStatus] = frozenset(
    {"succeeded", "failed", "cancelled"}
)
ALL_JOB_STATUSES: frozenset[ForecastJobStatus] = frozenset(
    {"queued", "running", "succeeded", "failed", "cancelled"}
)
ACTIVE_JOB_STATUSES: frozenset[ForecastJobStatus] = frozenset({"queued", "running"})


def is_terminal_job_status(status: ForecastJobStatus) -> bool:
    return status in TERMINAL_JOB_STATUSES


def is_active_job_status(status: ForecastJobStatus) -> bool:
    return status in ACTIVE_JOB_STATUSES
