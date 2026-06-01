from fastapi import APIRouter

from earth2_sandbox.config import Settings


def create_health_router(*, settings: Settings) -> APIRouter:
    router = APIRouter()

    @router.get("/")
    async def index() -> dict[str, str | dict[str, str]]:
        return {
            "service": settings.app_name,
            "status": "ok",
            "links": {
                "health": "/health",
                "docs": "/docs",
                "provider_status": "/api/v1/forecast/provider/status",
                "point_forecast": "/api/v1/forecast/point?latitude=37.5665&longitude=126.9780",
                "forecast_jobs": "/api/v1/forecast/jobs",
            },
        }

    @router.get("/health")
    async def health() -> dict[str, str | bool]:
        return {
            "status": "ok",
            "service": settings.app_name,
            "environment": settings.environment,
            "mock_forecast": settings.forecast_provider == "mock",
            "forecast_provider": settings.forecast_provider,
        }

    return router
