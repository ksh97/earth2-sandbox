import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from earth2_sandbox.api.http.v1.routers.forecast_jobs import create_forecast_jobs_router
from earth2_sandbox.api.http.v1.routers.forecast_queries import create_forecast_queries_router
from earth2_sandbox.api.http.v1.routers.health import create_health_router
from earth2_sandbox.api.http.v1.routers.provider_status import create_provider_status_router
from earth2_sandbox.config import Settings, get_settings
from earth2_sandbox.providers import build_forecast_provider
from earth2_sandbox.services.jobs import (
    FileForecastJobStore,
    ForecastJobService,
    InMemoryForecastJobStore,
)
from earth2_sandbox.workers import AsyncioTaskForecastJobWorker

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
    forecast_provider = forecast_provider_override or build_forecast_provider(settings)
    forecast_job_store = (
        FileForecastJobStore(settings.forecast_job_store_dir)
        if settings.forecast_job_store_backend == "file"
        else InMemoryForecastJobStore()
    )
    forecast_job_service = forecast_job_service_override or ForecastJobService(
        provider=forecast_provider,
        store=forecast_job_store,
        default_retention_hours=settings.forecast_job_retention_hours,
        default_stale_timeout_seconds=settings.forecast_job_stale_timeout_seconds,
    )
    recovered_job_tasks: set[asyncio.Task[None]] = set()

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        worker = AsyncioTaskForecastJobWorker(
            run_job=forecast_job_service.run_job,
            tasks=recovered_job_tasks,
        )
        await forecast_job_service.recover_interrupted_jobs(worker=worker)
        yield

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="Backend API for the Earth-2 weather forecast sandbox.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_DEV_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(create_health_router(settings=settings))
    app.include_router(create_provider_status_router(forecast_provider=forecast_provider))
    app.include_router(create_forecast_queries_router(forecast_provider=forecast_provider))
    app.include_router(create_forecast_jobs_router(forecast_job_service=forecast_job_service))

    return app
