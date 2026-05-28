from fastapi import FastAPI, Query

from earth2_sandbox.config import Settings, get_settings
from earth2_sandbox.services.forecast import MockForecastService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend API for the Earth-2 weather forecast sandbox.",
    )
    forecast_service = MockForecastService()

    @app.get("/health")
    async def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "service": settings.app_name,
            "environment": settings.environment,
            "mock_forecast": settings.enable_mock_forecast,
        }

    @app.get("/api/v1/forecast/sample")
    async def sample_forecast(
        latitude: float = Query(..., ge=-90, le=90),
        longitude: float = Query(..., ge=-180, le=180),
    ):
        return await forecast_service.get_point_forecast(latitude=latitude, longitude=longitude)

    return app

