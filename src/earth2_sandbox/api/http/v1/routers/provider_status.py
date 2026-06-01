from fastapi import APIRouter

from earth2_sandbox.providers import ForecastProvider
from earth2_sandbox.schemas.forecast import ForecastProviderStatus


def create_provider_status_router(*, forecast_provider: ForecastProvider) -> APIRouter:
    router = APIRouter(prefix="/api/v1/forecast", tags=["forecast"])

    @router.get("/provider/status", response_model=ForecastProviderStatus)
    async def forecast_provider_status() -> ForecastProviderStatus:
        return await forecast_provider.get_status()

    return router
