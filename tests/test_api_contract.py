from fastapi.testclient import TestClient

from earth2_sandbox.app import create_app

client = TestClient(create_app())


def test_health_contract() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "earth2-sandbox",
        "environment": "local",
        "mock_forecast": True,
    }


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


def test_sample_forecast_rejects_invalid_location() -> None:
    response = client.get(
        "/api/v1/forecast/sample",
        params={"latitude": 120, "longitude": 126.9780},
    )

    assert response.status_code == 422
