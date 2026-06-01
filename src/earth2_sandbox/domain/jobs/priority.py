from __future__ import annotations

from typing import Literal, TypeAlias

ForecastJobPriority: TypeAlias = Literal["low", "normal", "high"]

DEFAULT_FORECAST_JOB_PRIORITY: ForecastJobPriority = "normal"
FORECAST_JOB_PRIORITY_RANK: dict[ForecastJobPriority, int] = {
    "high": 0,
    "normal": 10,
    "low": 20,
}


def priority_rank(priority: ForecastJobPriority) -> int:
    return FORECAST_JOB_PRIORITY_RANK[priority]

