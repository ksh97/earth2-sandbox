from __future__ import annotations

from datetime import datetime
from typing import Protocol


class Clock(Protocol):
    """Application-facing source of current time."""

    def now(self) -> datetime: ...
