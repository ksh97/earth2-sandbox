from __future__ import annotations

from datetime import UTC, datetime


class SystemClock:
    """UTC clock adapter for production runtime wiring."""

    def now(self) -> datetime:
        return datetime.now(UTC)
