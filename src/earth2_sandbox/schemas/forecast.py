from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ForecastMetric(BaseModel):
    name: str
    value: float
    unit: str


class ForecastModelInfo(BaseModel):
    name: str
    version: str
    resolution: str
    run_mode: Literal["mock", "nim"]


class ForecastWindow(BaseModel):
    start_at: datetime
    end_at: datetime
    step_hours: int
    lead_hours: list[int]


class ForecastTimelineStep(BaseModel):
    lead_time_hours: int = Field(ge=0)
    valid_at: datetime
    temperature_c: float
    wind_speed_ms: float
    humidity_percent: float = Field(ge=0, le=100)
    precipitation_probability_percent: float = Field(ge=0, le=100)
    pressure_hpa: float
    confidence: float = Field(ge=0, le=1)
    condition: Literal["clear", "breezy", "humid", "rain_watch"]
    summary: str


class ForecastSignal(BaseModel):
    name: str
    level: Literal["low", "moderate", "elevated"]
    message: str


class ForecastSummary(BaseModel):
    provider: Literal["mock", "fourcastnet"]
    generated_at: datetime
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    headline: str
    metrics: list[ForecastMetric]
    model: ForecastModelInfo
    forecast_window: ForecastWindow
    timeline: list[ForecastTimelineStep]
    signals: list[ForecastSignal]


class ForecastProviderStatus(BaseModel):
    provider: Literal["mock", "fourcastnet"]
    mode: str
    configured: bool
    ready: bool
    supports_point_forecast: bool
    endpoint: str | None = None
    detail: str
