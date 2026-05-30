import asyncio

import httpx
from fastapi.testclient import TestClient

from earth2_sandbox.app import create_app
from earth2_sandbox.clients.nim import FourCastNetNimClient
from earth2_sandbox.config import Settings
from earth2_sandbox.providers import FourCastNetForecastProvider, build_forecast_provider
from earth2_sandbox.schemas.fourcastnet import FourCastNetHostedInferenceRequest


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


def test_hosted_fourcastnet_inference_posts_documented_payload() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers["authorization"]
        captured["accept"] = request.headers["accept"]
        captured["poll_seconds"] = request.headers["nvcf-poll-seconds"]
        captured["payload"] = request.read().decode()
        return httpx.Response(
            200,
            json={"request_id": "test-request", "status": "ok"},
            headers={"content-type": "application/json"},
        )

    client = FourCastNetNimClient(
        base_url="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
        mode="hosted",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    request = FourCastNetHostedInferenceRequest(
        variables=["w10m", "t2m"],
        accept="application/json",
        poll_seconds=7,
    )

    result = asyncio.run(client.run_hosted_inference(request))

    assert captured["url"] == "https://climate.api.nvidia.com/v1/nvidia/fourcastnet"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["accept"] == "application/json"
    assert captured["poll_seconds"] == "7"
    assert '"variables":"w10m,t2m"' in str(captured["payload"]).replace(" ", "")
    assert result.status_code == 200
    assert result.byte_length > 0
    assert result.json_preview == {"request_id": "test-request", "status": "ok"}


def test_hosted_fourcastnet_inference_requires_api_key() -> None:
    client = FourCastNetNimClient(
        base_url="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
        mode="hosted",
    )

    try:
        asyncio.run(client.run_hosted_inference(FourCastNetHostedInferenceRequest()))
    except RuntimeError as error:
        assert "API key is missing" in str(error)
    else:
        raise AssertionError("Expected hosted inference to require an API key.")


def test_build_forecast_provider_can_select_fourcastnet_hosted_mode() -> None:
    settings = Settings(
        forecast_provider="fourcastnet",
        fourcastnet_endpoint_mode="hosted",
        nvidia_api_key="test-key",
    )

    provider = build_forecast_provider(settings)
    status = asyncio.run(provider.get_status())

    assert isinstance(provider, FourCastNetForecastProvider)
    assert status.provider == "fourcastnet"
    assert status.mode == "hosted"
    assert status.ready is True
    assert status.supports_point_forecast is False


def test_hosted_inference_route_returns_adapter_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"fake tar bytes",
            headers={"content-type": "application/x-tar"},
        )

    settings = Settings(
        forecast_provider="fourcastnet",
        fourcastnet_endpoint_mode="hosted",
        nvidia_api_key="test-key",
    )
    provider = FourCastNetForecastProvider(
        client=FourCastNetNimClient(
            base_url="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
            mode="hosted",
            api_key="test-key",
            transport=httpx.MockTransport(handler),
        )
    )
    api_client = TestClient(
        create_app(settings=settings, forecast_provider_override=provider)
    )

    response = api_client.post(
        "/api/v1/forecast/fourcastnet/hosted/infer",
        json={"variables": ["w10m"], "simulation_length": 1},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["content_type"] == "application/x-tar"
    assert body["byte_length"] == len(b"fake tar bytes")
    assert body["request_payload"]["variables"] == "w10m"
    assert body["request_payload"]["simulation_length"] == 1
    assert body["post_processing"]["mobile_summary_ready"] is False
    assert body["post_processing"]["detected_format"] == "tar"
    assert "Decode returned tar archive" in body["post_processing"]["required_steps"][1]
    assert "Raw model output is intentionally not exposed" in body["post_processing"]["notes"][2]
