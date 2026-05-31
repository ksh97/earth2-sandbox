import tarfile
from io import BytesIO

import httpx
import numpy as np
from fastapi.testclient import TestClient

from earth2_sandbox.app import create_app
from earth2_sandbox.clients.nim import FourCastNetNimClient
from earth2_sandbox.config import Settings
from earth2_sandbox.providers import FourCastNetForecastProvider


def test_fourcastnet_job_exposes_asset_and_cache_diagnostics(tmp_path) -> None:
    content = _build_tar_bytes(
        {
            "000_000.npy": _build_point_array(
                wind_speed_ms=7,
                temperature_k=292.15,
                pressure_pa=101100,
                tcwv=36,
            ),
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
        fourcastnet_cache_dir=str(tmp_path),
    )
    provider = FourCastNetForecastProvider(
        client=FourCastNetNimClient(
            base_url="https://climate.api.nvidia.com/v1/nvidia/fourcastnet",
            mode="hosted",
            api_key="test-key",
            transport=httpx.MockTransport(handler),
        )
    )
    api_client = TestClient(create_app(settings=settings, forecast_provider_override=provider))

    response = api_client.post(
        "/api/v1/forecast/jobs",
        json={"latitude": 0, "longitude": 90},
    )

    assert response.status_code == 202
    job_url = response.json()["links"]["self"]
    job = api_client.get(job_url).json()

    assert job["status"] == "succeeded"
    assert job["forecast"]["provider"] == "fourcastnet"
    assert job["diagnostics"]["provider"] == "fourcastnet"
    assert job["diagnostics"]["response_source"] == "inline"
    assert job["diagnostics"]["cache_status"] == "disabled"
    assert job["diagnostics"]["byte_length"] == len(content)


def test_forecast_job_records_provider_failures() -> None:
    class FailingProvider:
        async def get_status(self):
            raise AssertionError("not used")

        async def get_point_forecast(self, *, latitude: float, longitude: float):
            raise RuntimeError("boom")

    api_client = TestClient(
        create_app(
            settings=Settings(forecast_provider="mock"),
            forecast_provider_override=FailingProvider(),
        )
    )

    response = api_client.post(
        "/api/v1/forecast/jobs",
        json={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert response.status_code == 202
    job = api_client.get(response.json()["links"]["self"]).json()

    assert job["status"] == "failed"
    assert "Unexpected forecast job error" in job["error"]


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
