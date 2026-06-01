from earth2_sandbox.application.ports.clock import Clock
from earth2_sandbox.bootstrap.settings import Settings
from earth2_sandbox.infrastructure.nvidia import FourCastNetForecastProvider, FourCastNetNimClient
from earth2_sandbox.infrastructure.providers import MockForecastProvider
from earth2_sandbox.providers.base import ForecastProvider
from earth2_sandbox.storage import FourCastNetResultCache


def build_forecast_provider(
    settings: Settings,
    *,
    clock: Clock | None = None,
) -> ForecastProvider:
    if settings.forecast_provider == "mock":
        return MockForecastProvider()

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
        status_url=settings.nvcf_status_url,
        max_poll_attempts=settings.nvcf_max_poll_attempts,
        poll_interval_seconds=settings.nvcf_poll_interval_seconds,
    )
    result_cache = (
        FourCastNetResultCache(settings.fourcastnet_cache_dir, clock=clock)
        if settings.fourcastnet_cache_enabled
        else None
    )
    return FourCastNetForecastProvider(client=client, result_cache=result_cache)
