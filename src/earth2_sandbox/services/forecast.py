"""Compatibility exports for forecast schemas and providers.

New code should import from `earth2_sandbox.schemas.forecast` and
`earth2_sandbox.providers`.
"""

from earth2_sandbox.providers import (
    ForecastProvider,
    ForecastProviderUnavailableError,
    FourCastNetForecastProvider,
    MockForecastProvider,
    build_forecast_provider,
)
from earth2_sandbox.providers.fourcastnet import FourCastNetForecastService
from earth2_sandbox.providers.mock import MockForecastService
from earth2_sandbox.schemas.forecast import (
    ForecastMetric,
    ForecastModelInfo,
    ForecastProviderStatus,
    ForecastSignal,
    ForecastSummary,
    ForecastTimelineStep,
    ForecastWindow,
)

__all__ = [
    "ForecastMetric",
    "ForecastModelInfo",
    "ForecastProvider",
    "ForecastProviderStatus",
    "ForecastProviderUnavailableError",
    "ForecastSignal",
    "ForecastSummary",
    "ForecastTimelineStep",
    "ForecastWindow",
    "FourCastNetForecastProvider",
    "FourCastNetForecastService",
    "MockForecastProvider",
    "MockForecastService",
    "build_forecast_provider",
]
