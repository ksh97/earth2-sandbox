from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from earth2_sandbox.config import Settings, get_settings
from earth2_sandbox.providers import (
    ForecastProviderUnavailableError,
    build_forecast_provider,
)
from earth2_sandbox.schemas.forecast import ForecastProviderStatus, ForecastSummary

LOCAL_DEV_ORIGINS = [
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:19006",
    "http://127.0.0.1:19006",
]


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend API for the Earth-2 weather forecast sandbox.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    forecast_provider = build_forecast_provider(settings)

    @app.get("/health")
    async def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "service": settings.app_name,
            "environment": settings.environment,
            "mock_forecast": settings.forecast_provider == "mock",
            "forecast_provider": settings.forecast_provider,
        }

    @app.get("/api/v1/forecast/provider/status", response_model=ForecastProviderStatus)
    async def forecast_provider_status() -> ForecastProviderStatus:
        return await forecast_provider.get_status()

    @app.get("/api/v1/forecast/sample", response_model=ForecastSummary)
    async def sample_forecast(
        latitude: float = Query(..., ge=-90, le=90),
        longitude: float = Query(..., ge=-180, le=180),
    ) -> ForecastSummary:
        try:
            return await forecast_provider.get_point_forecast(
                latitude=latitude,
                longitude=longitude,
            )
        except ForecastProviderUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    return app
