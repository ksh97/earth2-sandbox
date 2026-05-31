import asyncio
import tarfile
from io import BytesIO

import httpx
import numpy as np
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


def test_hosted_fourcastnet_inference_captures_large_asset_marker() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": "Large asset written"},
            headers={
                "content-type": "application/json",
                "nvcf-reqid": "test-request-id",
                "nvcf-status": "fulfilled",
            },
        )

    client = FourCastNetNimClient(
        base_url="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
        mode="hosted",
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.run_hosted_inference(FourCastNetHostedInferenceRequest()))

    assert result.large_asset_message == "Large asset written"
    assert result.nvcf_request_id == "test-request-id"
    assert result.nvcf_status == "fulfilled"


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
    assert status.supports_point_forecast is True


def test_hosted_fourcastnet_point_forecast_samples_tar_response() -> None:
    captured: dict[str, object] = {}
    content = _build_tar_bytes(
        {
            "000_000.npy": _build_point_array(
                wind_speed_ms=7,
                temperature_k=292.15,
                pressure_pa=101100,
                tcwv=36,
            ),
            "006_000.npy": _build_point_array(
                wind_speed_ms=8,
                temperature_k=293.15,
                pressure_pa=101000,
                tcwv=40,
            ),
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        captured["accept"] = request.headers["accept"]
        captured["payload"] = request.read().decode()
        return httpx.Response(
            200,
            content=content,
            headers={"content-type": "application/x-tar"},
        )

    provider = FourCastNetForecastProvider(
        client=FourCastNetNimClient(
            base_url="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
            mode="hosted",
            api_key="test-key",
            transport=httpx.MockTransport(handler),
        )
    )

    forecast = asyncio.run(provider.get_point_forecast(latitude=0, longitude=90))

    assert captured["accept"] == "application/x-tar"
    assert '"variables":"w10m,t2m,msl,tcwv,z500"' in str(captured["payload"]).replace(" ", "")
    assert forecast.provider == "fourcastnet"
    assert forecast.model.run_mode == "nim"
    assert forecast.forecast_window.lead_hours == [0, 6]
    assert forecast.timeline[0].temperature_c == 19.0
    assert forecast.timeline[0].wind_speed_ms == 7.0
    assert forecast.timeline[0].pressure_hpa == 1011.0


def test_hosted_fourcastnet_point_forecast_reports_large_asset_marker() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"message": "Large asset written"},
            headers={
                "content-type": "application/json",
                "nvcf-reqid": "test-request-id",
                "nvcf-status": "fulfilled",
            },
        )

    provider = FourCastNetForecastProvider(
        client=FourCastNetNimClient(
            base_url="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
            mode="hosted",
            api_key="test-key",
            transport=httpx.MockTransport(handler),
        )
    )

    try:
        asyncio.run(provider.get_point_forecast(latitude=0, longitude=90))
    except RuntimeError as error:
        assert "large asset marker" in str(error)
        assert "NVCF polling or redirect handling is not wired yet" in str(error)
    else:
        raise AssertionError("Expected large asset marker to block point forecast sampling.")


def test_hosted_inference_route_returns_adapter_result() -> None:
    content = _build_tar_bytes(
        {
            "000_000.npy": np.array([[[[1.0, 2.0]]]], dtype=np.float32),
            "006_000.npy": np.array([[[[3.0, 4.0]]]], dtype=np.float32),
        }
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=content,
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
    assert body["byte_length"] == len(content)
    assert body["request_payload"]["variables"] == "w10m"
    assert body["request_payload"]["simulation_length"] == 1
    assert body["decoded_tar"]["member_count"] == 2
    assert body["decoded_tar"]["lead_time_hours"] == [0, 6]
    assert body["decoded_tar"]["arrays"][0]["shape"] == [1, 1, 1, 2]
    assert body["post_processing"]["mobile_summary_ready"] is False
    assert body["post_processing"]["detected_format"] == "tar"
    assert "Use decoded NumPy member metadata" in body["post_processing"]["required_steps"][1]
    assert "Raw model output is intentionally not exposed" in body["post_processing"]["notes"][3]


def _build_tar_bytes(entries: dict[str, np.ndarray]) -> bytes:
    buffer = BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for filename, array in entries.items():
            array_buffer = BytesIO()
            np.save(array_buffer, array)
            data = array_buffer.getvalue()
            info = tarfile.TarInfo(filename)
            info.size = len(data)
            archive.addfile(info, BytesIO(data))

    return buffer.getvalue()


def _build_point_array(
    *,
    wind_speed_ms: float,
    temperature_k: float,
    pressure_pa: float,
    tcwv: float,
) -> np.ndarray:
    array = np.zeros((1, 5, 3, 4), dtype=np.float32)
    latitude_index = 1
    longitude_index = 1
    array[0, 0, latitude_index, longitude_index] = wind_speed_ms
    array[0, 1, latitude_index, longitude_index] = temperature_k
    array[0, 2, latitude_index, longitude_index] = pressure_pa
    array[0, 3, latitude_index, longitude_index] = tcwv
    array[0, 4, latitude_index, longitude_index] = 5500
    return array
