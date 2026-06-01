from __future__ import annotations

from collections.abc import Collection

from earth2_sandbox.domain.jobs.status import ForecastJobStatus


class ForecastJobNotFoundError(KeyError):
    """Raised when a forecast job id is unknown to the configured job store."""


class ForecastJobConflictError(RuntimeError):
    """Raised when a job state transition is not valid for the current status."""


class ForecastJobTransitionError(ForecastJobConflictError):
    """Raised when a conditional job update observes a different current status."""

    def __init__(
        self,
        *,
        job_id: str,
        current_status: ForecastJobStatus,
        expected_statuses: Collection[ForecastJobStatus],
    ) -> None:
        self.job_id = job_id
        self.current_status = current_status
        self.expected_statuses = frozenset(expected_statuses)
        expected = ", ".join(sorted(self.expected_statuses))
        super().__init__(
            f"Cannot transition forecast job {job_id} from {current_status}; "
            f"expected one of: {expected}."
        )
