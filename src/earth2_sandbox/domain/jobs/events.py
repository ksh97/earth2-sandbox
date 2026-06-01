from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from earth2_sandbox.domain.jobs.status import ForecastJobStatus


@dataclass(frozen=True, slots=True)
class ForecastJobEventRecord:
    occurred_at: datetime
    status: ForecastJobStatus
    message: str


def record_forecast_job_event(
    *,
    status: ForecastJobStatus,
    message: str,
    occurred_at: datetime | None = None,
) -> ForecastJobEventRecord:
    return ForecastJobEventRecord(
        occurred_at=occurred_at or datetime.now(UTC),
        status=status,
        message=message,
    )
