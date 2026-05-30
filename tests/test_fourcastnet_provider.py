import asyncio

import httpx

from earth2_sandbox.clients.nim import FourCastNetNimClient
from earth2_sandbox.config import Settings
from earth2_sandbox.services.forecast import FourCastNetForecastService, build_forecast_provider


def test_self_hosted_fourcastnet_readiness_uses_ready_endpoint() -> None:
    requested_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested_urls.append(str(request.url))
        return httpx.Response(200, json={"status": "ready"})

    client = FourCastNetNimClient(
        base_url="http://fourcastnet-nim.example",
        timeout_seconds=1,
        transport=httpx.MockTransport(handler),
    )

    status = asyncio.run(client.get_readiness_status())

    assert status.ready is True
    assert status.status_code == 200
    assert requested_urls == ["http://fourcastnet-nim.example/v1/health/ready"]


def test_hosted_fourcastnet_status_uses_api_key_configuration() -> None:
    client = FourCastNetNimClient(
        base_url="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
        mode="hosted",
        api_key="test-key",
    )

    status = asyncio.run(client.get_readiness_status())

    assert status.ready is True
    assert status.configured is True
    assert status.endpoint == "https://climate.api.nvidia.com/v1/nvidia/fourcastnet"


def test_hosted_fourcastnet_payload_matches_documented_shape() -> None:
    client = FourCastNetNimClient(
        base_url="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
        mode="hosted",
        api_key="test-key",
    )

    payload = client.build_hosted_inference_payload(
        variables=("t2m", "w10m"),
        simulation_length=4,
        ensemble_size=1,
    )

    assert payload == {
        "input_id": 0,
        "variables": "t2m,w10m",
        "simulation_length": 4,
        "ensemble_size": 1,
        "noise_amplitude": 0,
    }


def test_build_forecast_provider_can_select_fourcastnet_hosted_mode() -> None:
    settings = Settings(
        forecast_provider="fourcastnet",
        fourcastnet_endpoint_mode="hosted",
        nvidia_api_key="test-key",
    )

    provider = build_forecast_provider(settings)
    status = asyncio.run(provider.get_status())

    assert isinstance(provider, FourCastNetForecastService)
    assert status.provider == "fourcastnet"
    assert status.mode == "hosted"
    assert status.ready is True
    assert status.supports_point_forecast is False
