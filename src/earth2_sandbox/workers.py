"""Compatibility exports for forecast job worker ports and local adapters."""

from earth2_sandbox.application.ports.forecast_job_worker import (
    ForecastJobWorker,
    RunForecastJobCallback,
)
from earth2_sandbox.infrastructure.queue import (
    AsyncioTaskForecastJobWorker,
    DeferredForecastJobWorker,
    QueuedAsyncioTaskForecastJobWorker,
    QueuedDeferredForecastJobWorker,
)

RunForecastJob = RunForecastJobCallback

__all__ = [
    "AsyncioTaskForecastJobWorker",
    "DeferredForecastJobWorker",
    "ForecastJobWorker",
    "QueuedAsyncioTaskForecastJobWorker",
    "QueuedDeferredForecastJobWorker",
    "RunForecastJob",
    "RunForecastJobCallback",
]
