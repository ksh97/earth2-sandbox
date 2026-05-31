from fastapi.testclient import TestClient

from earth2_sandbox.app import create_app
from earth2_sandbox.config import Settings

client = TestClient(create_app())


def test_health_contract() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "earth2-sandbox",
        "environment": "local",
        "mock_forecast": True,
        "forecast_provider": "mock",
    }


def test_health_allows_local_mobile_preview_origin() -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:8081"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8081"


def test_sample_forecast_contract() -> None:
    response = client.get(
        "/api/v1/forecast/sample",
        params={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["latitude"] == 37.5665
    assert body["longitude"] == 126.9780
    assert body["headline"]
    assert "generated_at" in body
    assert {metric["name"] for metric in body["metrics"]} == {
        "temperature",
        "wind_speed",
        "humidity",
    }


def test_point_forecast_contract() -> None:
    response = client.get(
        "/api/v1/forecast/point",
        params={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "mock"
    assert body["latitude"] == 37.5665
    assert body["longitude"] == 126.9780


def test_sample_forecast_rejects_invalid_location() -> None:
    response = client.get(
        "/api/v1/forecast/sample",
        params={"latitude": 120, "longitude": 126.9780},
    )

    assert response.status_code == 422


def test_fourcastnet_misconfiguration_keeps_health_available() -> None:
    app = create_app(
        Settings(
            enable_mock_forecast=False,
            fourcastnet_input_array_path=None,
        )
    )
    local_client = TestClient(app)

    health_response = local_client.get("/health")
    forecast_response = local_client.get(
        "/api/v1/forecast/point",
        params={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert health_response.status_code == 200
    assert health_response.json()["forecast_provider"] == "fourcastnet"
    assert forecast_response.status_code == 503
    assert "EARTH2_FOURCASTNET_INPUT_ARRAY_PATH" in forecast_response.json()["detail"]
