from fastapi.testclient import TestClient

from earth2_sandbox.app import create_app
from earth2_sandbox.config import Settings

client = TestClient(
    create_app(
        settings=Settings(
            forecast_provider="mock",
            fourcastnet_endpoint_mode="self_hosted",
            nvidia_api_key=None,
        )
    )
)


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


def test_index_contract() -> None:
    response = client.get("/")

    assert response.status_code == 200
    body = response.json()
    assert body["service"] == "earth2-sandbox"
    assert body["status"] == "ok"
    assert body["links"]["health"] == "/health"
    assert body["links"]["docs"] == "/docs"
    assert body["links"]["provider_status"] == "/api/v1/forecast/provider/status"
    assert body["links"]["point_forecast"].startswith("/api/v1/forecast/point")
    assert body["links"]["forecast_jobs"] == "/api/v1/forecast/jobs"


def test_health_allows_local_mobile_preview_origin() -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:8081"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:8081"


def test_sample_forecast_contract() -> None:
    response = client.get(
        "/api/v1/forecast/sample",
        params={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert_forecast_contract(response)


def test_point_forecast_contract() -> None:
    response = client.get(
        "/api/v1/forecast/point",
        params={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert_forecast_contract(response)


def test_forecast_job_contract() -> None:
    response = client.post(
        "/api/v1/forecast/jobs",
        json={"latitude": 37.5665, "longitude": 126.9780},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["latitude"] == 37.5665
    assert body["longitude"] == 126.9780
    assert body["forecast"] is None
    assert body["links"]["self"].startswith("/api/v1/forecast/jobs/")

    job_response = client.get(body["links"]["self"])

    assert job_response.status_code == 200
    job = job_response.json()
    assert job["id"] == body["id"]
    assert job["status"] == "succeeded"
    assert job["forecast"]["provider"] == "mock"
    assert job["diagnostics"]["provider"] == "mock"
    assert job["diagnostics"]["message"] == "Forecast summary is ready."


def test_forecast_job_missing_id_returns_404() -> None:
    response = client.get("/api/v1/forecast/jobs/missing")

    assert response.status_code == 404
    assert response.json()["detail"] == "Forecast job not found."


def assert_forecast_contract(response) -> None:
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
    assert body["model"]["run_mode"] == "mock"
    assert body["forecast_window"]["lead_hours"] == [0, 6, 12, 24, 36, 48, 72]
    assert len(body["timeline"]) == 7
    assert {
        "lead_time_hours",
        "valid_at",
        "temperature_c",
        "wind_speed_ms",
        "humidity_percent",
        "precipitation_probability_percent",
        "pressure_hpa",
        "confidence",
        "condition",
        "summary",
    }.issubset(body["timeline"][0])
    assert {signal["name"] for signal in body["signals"]} == {
        "Precipitation",
        "Wind",
        "Model confidence",
    }


def test_forecast_provider_status_contract() -> None:
    response = client.get("/api/v1/forecast/provider/status")

    assert response.status_code == 200
    assert response.json() == {
        "provider": "mock",
        "mode": "deterministic",
        "configured": True,
        "ready": True,
        "supports_point_forecast": True,
        "endpoint": None,
        "detail": "Deterministic mock forecast provider is ready.",
    }


def test_sample_forecast_rejects_invalid_location() -> None:
    response = client.get(
        "/api/v1/forecast/sample",
        params={"latitude": 120, "longitude": 126.9780},
    )

    assert response.status_code == 422


def test_point_forecast_rejects_invalid_location() -> None:
    response = client.get(
        "/api/v1/forecast/point",
        params={"latitude": 120, "longitude": 126.9780},
    )

    assert response.status_code == 422
