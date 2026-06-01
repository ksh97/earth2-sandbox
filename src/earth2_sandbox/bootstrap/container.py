from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from earth2_sandbox.bootstrap.settings import Settings, get_settings
from earth2_sandbox.providers import ForecastProvider, build_forecast_provider
from earth2_sandbox.services.jobs import (
    FileForecastJobStore,
    ForecastJobService,
    ForecastJobStore,
    InMemoryForecastJobStore,
)


@dataclass
class ApplicationContainer:
    """Runtime dependency container for the API process."""

    settings: Settings
    forecast_provider: ForecastProvider
    forecast_job_store: ForecastJobStore
    forecast_job_service: ForecastJobService
    recovered_job_tasks: set[asyncio.Task[None]] = field(default_factory=set)


def build_container(
    *,
    settings: Settings | None = None,
    forecast_provider_override: ForecastProvider | None = None,
    forecast_job_service_override: ForecastJobService | None = None,
) -> ApplicationContainer:
    resolved_settings = settings or get_settings()
    forecast_provider = forecast_provider_override or build_forecast_provider(resolved_settings)
    forecast_job_store = build_forecast_job_store(resolved_settings)
    forecast_job_service = forecast_job_service_override or ForecastJobService(
        provider=forecast_provider,
        store=forecast_job_store,
        default_retention_hours=resolved_settings.forecast_job_retention_hours,
        default_stale_timeout_seconds=resolved_settings.forecast_job_stale_timeout_seconds,
    )
    return ApplicationContainer(
        settings=resolved_settings,
        forecast_provider=forecast_provider,
        forecast_job_store=forecast_job_store,
        forecast_job_service=forecast_job_service,
    )


def build_forecast_job_store(settings: Settings) -> ForecastJobStore:
    if settings.forecast_job_store_backend == "file":
        return FileForecastJobStore(settings.forecast_job_store_dir)

    return InMemoryForecastJobStore()
