from typing import Protocol

from earth2_sandbox.schemas.forecast import ForecastProviderStatus, ForecastSummary


class ForecastProviderUnavailableError(RuntimeError):
    """Raised when the selected forecast provider cannot serve a point forecast yet."""


class ForecastProvider(Protocol):
    async def get_point_forecast(self, latitude: float, longitude: float) -> ForecastSummary: ...

    async def get_status(self) -> ForecastProviderStatus: ...
