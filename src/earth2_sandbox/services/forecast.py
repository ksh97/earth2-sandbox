from datetime import UTC, datetime
from math import cos, radians, sin
from typing import Literal

from pydantic import BaseModel, Field


class ForecastMetric(BaseModel):
    name: str
    value: float
    unit: str


class ForecastSummary(BaseModel):
    provider: Literal["mock", "fourcastnet"]
    generated_at: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    headline: str
    metrics: list[ForecastMetric]


class MockForecastService:
    """Deterministic forecast values for API and mobile UI development."""

    async def get_point_forecast(self, latitude: float, longitude: float) -> ForecastSummary:
        latitude_factor = sin(radians(latitude))
        longitude_factor = cos(radians(longitude))
        temperature_c = round(18 + 10 * latitude_factor + 2 * longitude_factor, 1)
        wind_speed_ms = round(4 + abs(latitude_factor * longitude_factor) * 8, 1)
        humidity_percent = round(55 + abs(longitude_factor) * 25, 1)

        return ForecastSummary(
            provider="mock",
            generated_at=datetime.now(UTC),
            latitude=latitude,
            longitude=longitude,
            headline="Mock forecast for UI and API development",
            metrics=[
                ForecastMetric(name="temperature", value=temperature_c, unit="celsius"),
                ForecastMetric(name="wind_speed", value=wind_speed_ms, unit="m/s"),
                ForecastMetric(name="humidity", value=humidity_percent, unit="percent"),
            ],
        )

