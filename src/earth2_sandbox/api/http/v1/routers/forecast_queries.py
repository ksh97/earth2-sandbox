from fastapi import APIRouter, HTTPException, Query

from earth2_sandbox.providers import (
    ForecastProvider,
    ForecastProviderUnavailableError,
    FourCastNetForecastProvider,
)
from earth2_sandbox.schemas.forecast import ForecastSummary
from earth2_sandbox.schemas.fourcastnet import (
    FourCastNetHostedInferenceRequest,
    FourCastNetHostedInferenceResult,
)


def create_forecast_queries_router(*, forecast_provider: ForecastProvider) -> APIRouter:
    router = APIRouter(prefix="/api/v1/forecast", tags=["forecast"])

    async def point_forecast_response(latitude: float, longitude: float) -> ForecastSummary:
        try:
            return await forecast_provider.get_point_forecast(
                latitude=latitude,
                longitude=longitude,
            )
        except ForecastProviderUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @router.get("/point", response_model=ForecastSummary)
    async def point_forecast(
        latitude: float = Query(..., ge=-90, le=90),
        longitude: float = Query(..., ge=-180, le=180),
    ) -> ForecastSummary:
        return await point_forecast_response(latitude=latitude, longitude=longitude)

    @router.get("/sample", response_model=ForecastSummary)
    async def sample_forecast(
        latitude: float = Query(..., ge=-90, le=90),
        longitude: float = Query(..., ge=-180, le=180),
    ) -> ForecastSummary:
        return await point_forecast_response(latitude=latitude, longitude=longitude)

    @router.post(
        "/fourcastnet/hosted/infer",
        response_model=FourCastNetHostedInferenceResult,
    )
    async def hosted_fourcastnet_inference(
        request: FourCastNetHostedInferenceRequest,
    ) -> FourCastNetHostedInferenceResult:
        if not isinstance(forecast_provider, FourCastNetForecastProvider):
            raise HTTPException(
                status_code=409,
                detail="Select EARTH2_FORECAST_PROVIDER=fourcastnet to run hosted inference.",
            )

        try:
            return await forecast_provider.run_hosted_inference(request)
        except ForecastProviderUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    return router
