from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from earth2_sandbox.api.http.v1.routers.forecast_jobs import create_forecast_jobs_router
from earth2_sandbox.api.http.v1.routers.forecast_queries import create_forecast_queries_router
from earth2_sandbox.api.http.v1.routers.health import create_health_router
from earth2_sandbox.api.http.v1.routers.provider_status import create_provider_status_router
from earth2_sandbox.bootstrap.container import ApplicationContainer, build_container
from earth2_sandbox.bootstrap.settings import Settings
from earth2_sandbox.infrastructure.queue import AsyncioTaskForecastJobWorker
from earth2_sandbox.providers import ForecastProvider
from earth2_sandbox.services.jobs import ForecastJobService

LOCAL_DEV_ORIGINS = [
    "http://localhost:8081",
    "http://127.0.0.1:8081",
    "http://localhost:19006",
    "http://127.0.0.1:19006",
]


def create_app(
    settings: Settings | None = None,
    forecast_provider_override: ForecastProvider | None = None,
    forecast_job_service_override: ForecastJobService | None = None,
) -> FastAPI:
    container = build_container(
        settings=settings,
        forecast_provider_override=forecast_provider_override,
        forecast_job_service_override=forecast_job_service_override,
    )
    return create_app_from_container(container)


def create_app_from_container(container: ApplicationContainer) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        worker = AsyncioTaskForecastJobWorker(
            run_job=container.forecast_job_service.run_job,
            tasks=container.recovered_job_tasks,
        )
        await container.forecast_job_service.recover_interrupted_jobs(worker=worker)
        yield

    app = FastAPI(
        title=container.settings.app_name,
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
    app.include_router(create_health_router(settings=container.settings))
    app.include_router(
        create_provider_status_router(forecast_provider=container.forecast_provider)
    )
    app.include_router(create_forecast_queries_router(forecast_provider=container.forecast_provider))
    app.include_router(
        create_forecast_jobs_router(forecast_job_service=container.forecast_job_service)
    )

    return app
