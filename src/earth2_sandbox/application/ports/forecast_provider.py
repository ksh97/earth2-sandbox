from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from earth2_sandbox.schemas.forecast import ForecastProviderStatus, ForecastSummary


class ForecastProviderUnavailableError(RuntimeError):
    """Raised when the selected forecast provider cannot serve a point forecast yet."""

    def __init__(self, message: str, *, diagnostics: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.diagnostics = diagnostics or {"message": message}


@dataclass(frozen=True)
class ForecastProviderResult:
    summary: ForecastSummary
    diagnostics: dict[str, Any]


class ForecastProvider(Protocol):
    async def get_point_forecast(self, latitude: float, longitude: float) -> ForecastSummary: ...

    async def get_status(self) -> ForecastProviderStatus: ...
