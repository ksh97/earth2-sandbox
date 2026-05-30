from datetime import UTC, datetime, timedelta
from math import cos, radians, sin
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from earth2_sandbox.clients.nim import FourCastNetNimClient
from earth2_sandbox.config import Settings


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


class ForecastProviderUnavailableError(RuntimeError):
    """Raised when the selected forecast provider cannot serve a point forecast yet."""


class ForecastProvider(Protocol):
    async def get_point_forecast(self, latitude: float, longitude: float) -> ForecastSummary: ...

    async def get_status(self) -> ForecastProviderStatus: ...


class MockForecastService:
    """Deterministic forecast values for API and mobile UI development."""

    async def get_status(self) -> ForecastProviderStatus:
        return ForecastProviderStatus(
            provider="mock",
            mode="deterministic",
            configured=True,
            ready=True,
            supports_point_forecast=True,
            detail="Deterministic mock forecast provider is ready.",
        )

    async def get_point_forecast(self, latitude: float, longitude: float) -> ForecastSummary:
        latitude_factor = sin(radians(latitude))
        longitude_factor = cos(radians(longitude))
        temperature_c = round(18 + 10 * latitude_factor + 2 * longitude_factor, 1)
        wind_speed_ms = round(4 + abs(latitude_factor * longitude_factor) * 8, 1)
        humidity_percent = round(55 + abs(longitude_factor) * 25, 1)
        generated_at = datetime.now(UTC)
        lead_hours = [0, 6, 12, 24, 36, 48, 72]
        timeline = [
            self._build_timeline_step(
                lead_time_hours=lead_time_hours,
                generated_at=generated_at,
                latitude=latitude,
                longitude=longitude,
                base_temperature_c=temperature_c,
                base_wind_speed_ms=wind_speed_ms,
                base_humidity_percent=humidity_percent,
            )
            for lead_time_hours in lead_hours
        ]

        return ForecastSummary(
            provider="mock",
            generated_at=generated_at,
            latitude=latitude,
            longitude=longitude,
            headline=self._build_headline(timeline[0]),
            metrics=[
                ForecastMetric(name="temperature", value=temperature_c, unit="celsius"),
                ForecastMetric(name="wind_speed", value=wind_speed_ms, unit="m/s"),
                ForecastMetric(name="humidity", value=humidity_percent, unit="percent"),
            ],
            model=ForecastModelInfo(
                name="FourCastNet-compatible mock",
                version="0.1.0",
                resolution="0.25 degree grid equivalent",
                run_mode="mock",
            ),
            forecast_window=ForecastWindow(
                start_at=generated_at,
                end_at=generated_at + timedelta(hours=lead_hours[-1]),
                step_hours=6,
                lead_hours=lead_hours,
            ),
            timeline=timeline,
            signals=self._build_signals(timeline),
        )

    def _build_timeline_step(
        self,
        *,
        lead_time_hours: int,
        generated_at: datetime,
        latitude: float,
        longitude: float,
        base_temperature_c: float,
        base_wind_speed_ms: float,
        base_humidity_percent: float,
    ) -> ForecastTimelineStep:
        latitude_wave = sin(radians(latitude + lead_time_hours * 7))
        longitude_wave = cos(radians(longitude - lead_time_hours * 4))
        temperature_c = round(base_temperature_c + latitude_wave * 3.2, 1)
        wind_speed_ms = round(base_wind_speed_ms + abs(longitude_wave) * 1.8, 1)
        humidity_percent = round(
            min(96, max(25, base_humidity_percent + longitude_wave * 7)),
            1,
        )
        precipitation_probability_percent = round(
            min(92, max(3, 16 + (humidity_percent - 55) * 0.75 + lead_time_hours * 0.18)),
            1,
        )
        pressure_hpa = round(
            1013.2 + longitude_wave * 5 - precipitation_probability_percent * 0.035,
            1,
        )
        confidence = round(max(0.62, 0.95 - lead_time_hours * 0.0038), 2)
        condition = self._choose_condition(
            wind_speed_ms=wind_speed_ms,
            humidity_percent=humidity_percent,
            precipitation_probability_percent=precipitation_probability_percent,
        )

        return ForecastTimelineStep(
            lead_time_hours=lead_time_hours,
            valid_at=generated_at + timedelta(hours=lead_time_hours),
            temperature_c=temperature_c,
            wind_speed_ms=wind_speed_ms,
            humidity_percent=humidity_percent,
            precipitation_probability_percent=precipitation_probability_percent,
            pressure_hpa=pressure_hpa,
            confidence=confidence,
            condition=condition,
            summary=self._build_step_summary(
                condition=condition,
                temperature_c=temperature_c,
                wind_speed_ms=wind_speed_ms,
                precipitation_probability_percent=precipitation_probability_percent,
            ),
        )

    def _choose_condition(
        self,
        *,
        wind_speed_ms: float,
        humidity_percent: float,
        precipitation_probability_percent: float,
    ) -> Literal["clear", "breezy", "humid", "rain_watch"]:
        if precipitation_probability_percent >= 45:
            return "rain_watch"
        if wind_speed_ms >= 8:
            return "breezy"
        if humidity_percent >= 74:
            return "humid"

        return "clear"

    def _build_headline(self, current_step: ForecastTimelineStep) -> str:
        if current_step.condition == "rain_watch":
            return "Rain risk is rising in the mock forecast window."
        if current_step.condition == "breezy":
            return "Breezy conditions lead this mock forecast."
        if current_step.condition == "humid":
            return "Humid air dominates the current mock forecast."

        return "Stable mock forecast for UI and API development."

    def _build_step_summary(
        self,
        *,
        condition: Literal["clear", "breezy", "humid", "rain_watch"],
        temperature_c: float,
        wind_speed_ms: float,
        precipitation_probability_percent: float,
    ) -> str:
        condition_text = {
            "clear": "Stable conditions",
            "breezy": "Breezy air flow",
            "humid": "Humid conditions",
            "rain_watch": "Rain watch signal",
        }[condition]
        return (
            f"{condition_text}: {temperature_c} C, wind {wind_speed_ms} m/s, "
            f"rain chance {precipitation_probability_percent}%."
        )

    def _build_signals(self, timeline: list[ForecastTimelineStep]) -> list[ForecastSignal]:
        max_rain = max(step.precipitation_probability_percent for step in timeline)
        max_wind = max(step.wind_speed_ms for step in timeline)
        min_confidence = min(step.confidence for step in timeline)
        signals = [
            ForecastSignal(
                name="Precipitation",
                level="elevated" if max_rain >= 55 else "moderate" if max_rain >= 35 else "low",
                message=f"Peak mock rain chance reaches {max_rain}%.",
            ),
            ForecastSignal(
                name="Wind",
                level="moderate" if max_wind >= 9 else "low",
                message=f"Peak mock wind speed reaches {max_wind} m/s.",
            ),
            ForecastSignal(
                name="Model confidence",
                level="moderate" if min_confidence < 0.78 else "low",
                message=f"Lowest confidence across the window is {round(min_confidence * 100)}%.",
            ),
        ]
        return signals


class FourCastNetForecastService:
    """FourCastNet provider boundary for readiness checks and future inference wiring."""

    def __init__(self, client: FourCastNetNimClient):
        self.client = client

    async def get_status(self) -> ForecastProviderStatus:
        status = await self.client.get_readiness_status()
        return ForecastProviderStatus(
            provider="fourcastnet",
            mode=status.mode,
            configured=status.configured,
            ready=status.ready,
            supports_point_forecast=False,
            endpoint=status.endpoint,
            detail=(
                f"{status.detail} Point forecast post-processing is not implemented yet."
            ).strip(),
        )

    async def get_point_forecast(self, latitude: float, longitude: float) -> ForecastSummary:
        status = await self.get_status()
        detail = (
            status.detail
            if status.ready
            else "FourCastNet provider is not ready. Use mock provider until NIM is configured."
        )
        raise ForecastProviderUnavailableError(detail)


def build_forecast_provider(settings: Settings) -> ForecastProvider:
    if settings.forecast_provider == "mock":
        return MockForecastService()

    api_key = settings.nvidia_api_key.get_secret_value() if settings.nvidia_api_key else None
    base_url = (
        settings.fourcastnet_hosted_url
        if settings.fourcastnet_endpoint_mode == "hosted"
        else settings.nim_base_url
    )
    client = FourCastNetNimClient(
        base_url=base_url,
        timeout_seconds=settings.request_timeout_seconds,
        mode=settings.fourcastnet_endpoint_mode,
        api_key=api_key,
    )
    return FourCastNetForecastService(client=client)

