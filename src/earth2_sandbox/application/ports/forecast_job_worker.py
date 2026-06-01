from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Protocol

RunForecastJobCallback = Callable[[str], Awaitable[None]]


class ForecastJobWorker(Protocol):
    """Port for scheduling forecast job execution outside the API command path."""

    def enqueue(self, job_id: str) -> None: ...
