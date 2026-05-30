from earth2_sandbox.clients.nim import FourCastNetNimClient
from earth2_sandbox.config import Settings
from earth2_sandbox.providers.base import ForecastProvider
from earth2_sandbox.providers.fourcastnet import FourCastNetForecastProvider
from earth2_sandbox.providers.mock import MockForecastProvider


def build_forecast_provider(settings: Settings) -> ForecastProvider:
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
    )
    return FourCastNetForecastProvider(client=client)
