from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware

from earth2_sandbox.config import Settings, get_settings
from earth2_sandbox.providers import (
    ForecastProviderUnavailableError,
    FourCastNetForecastProvider,
    build_forecast_provider,
)
from earth2_sandbox.schemas.forecast import ForecastProviderStatus, ForecastSummary
from earth2_sandbox.schemas.fourcastnet import (
    FourCastNetHostedInferenceRequest,
    FourCastNetHostedInferenceResult,
)
from earth2_sandbox.schemas.jobs import (
    ForecastJob,
    ForecastJobCreateRequest,
    ForecastJobListResponse,
    ForecastJobStatus,
)
from earth2_sandbox.services.jobs import (
    FileForecastJobStore,
    ForecastJobNotFoundError,
    ForecastJobService,
    InMemoryForecastJobStore,
)

LOCAL_DEV_ORIGINS = [
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:19006",
    "http://127.0.0.1:19006",
]


def create_app(
    settings: Settings | None = None,
    forecast_provider_override: object | None = None,
    forecast_job_service_override: ForecastJobService | None = None,
) -> FastAPI:
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
    forecast_provider = forecast_provider_override or build_forecast_provider(settings)
    forecast_job_store = (
        FileForecastJobStore(settings.forecast_job_store_dir)
        if settings.forecast_job_store_backend == "file"
        else InMemoryForecastJobStore()
    )
    forecast_job_service = forecast_job_service_override or ForecastJobService(
        provider=forecast_provider,
        store=forecast_job_store,
    )

    @app.get("/")
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

    async def point_forecast_response(latitude: float, longitude: float) -> ForecastSummary:
        try:
            return await forecast_provider.get_point_forecast(
                latitude=latitude,
                longitude=longitude,
            )
        except ForecastProviderUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error

    @app.get("/api/v1/forecast/point", response_model=ForecastSummary)
    async def point_forecast(
        latitude: float = Query(..., ge=-90, le=90),
        longitude: float = Query(..., ge=-180, le=180),
    ) -> ForecastSummary:
        return await point_forecast_response(latitude=latitude, longitude=longitude)

    @app.get("/api/v1/forecast/sample", response_model=ForecastSummary)
    async def sample_forecast(
        latitude: float = Query(..., ge=-90, le=90),
        longitude: float = Query(..., ge=-180, le=180),
    ) -> ForecastSummary:
        return await point_forecast_response(latitude=latitude, longitude=longitude)

    @app.post(
        "/api/v1/forecast/jobs",
        response_model=ForecastJob,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def create_forecast_job(
        request: ForecastJobCreateRequest,
        background_tasks: BackgroundTasks,
    ) -> ForecastJob:
        job = await forecast_job_service.create_job(
            latitude=request.latitude,
            longitude=request.longitude,
        )
        background_tasks.add_task(forecast_job_service.run_job, job.id)
        return job

    @app.get("/api/v1/forecast/jobs", response_model=ForecastJobListResponse)
    async def list_forecast_jobs(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        job_status: Annotated[ForecastJobStatus | None, Query(alias="status")] = None,
    ) -> ForecastJobListResponse:
        return await forecast_job_service.list_recent_jobs(
            limit=limit,
            status=job_status,
        )

    @app.get("/api/v1/forecast/jobs/{job_id}", response_model=ForecastJob)
    async def get_forecast_job(job_id: str) -> ForecastJob:
        try:
            return await forecast_job_service.get_job(job_id)
        except ForecastJobNotFoundError as error:
            raise HTTPException(status_code=404, detail="Forecast job not found.") from error

    @app.post(
        "/api/v1/forecast/fourcastnet/hosted/infer",
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

    return app
