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
    assert [event["status"] for event in body["events"]] == ["queued"]
    assert body["links"]["self"].startswith("/api/v1/forecast/jobs/")
    assert body["links"]["poll"].endswith("/poll")
    assert body["links"]["retry"].endswith("/retry")
    assert body["links"]["cancel"].endswith("/cancel")

    job_response = client.get(body["links"]["self"])

    assert job_response.status_code == 200
    job = job_response.json()
    assert job["id"] == body["id"]
    assert job["status"] == "succeeded"
    assert job["forecast"]["provider"] == "mock"
    assert job["diagnostics"]["provider"] == "mock"
    assert job["diagnostics"]["message"] == "Forecast summary is ready."
    assert [event["status"] for event in job["events"]] == ["queued", "running", "succeeded"]


def test_forecast_job_poll_contract() -> None:
    response = client.post(
        "/api/v1/forecast/jobs",
        json={"latitude": 37.5665, "longitude": 126.9780},
    )
    created = response.json()

    poll_response = client.get(created["links"]["poll"])

    assert poll_response.status_code == 200
    body = poll_response.json()
    assert body["id"] == created["id"]
    assert body["status"] == "succeeded"
    assert body["terminal"] is True
    assert body["forecast_ready"] is True
    assert body["retry_after_seconds"] is None
    assert body["event_count"] == 3
    assert body["latest_event"]["status"] == "succeeded"
    assert body["links"]["self"] == created["links"]["self"]


def test_forecast_jobs_list_contract() -> None:
    response = client.post(
        "/api/v1/forecast/jobs",
        json={"latitude": 35.6762, "longitude": 139.6503},
    )
    created = response.json()

    list_response = client.get("/api/v1/forecast/jobs", params={"limit": 1})

    assert list_response.status_code == 200
    body = list_response.json()
    assert body["count"] == 1
    assert body["jobs"][0]["id"] == created["id"]
    assert body["jobs"][0]["links"]["self"] == created["links"]["self"]
    assert "forecast" not in body["jobs"][0]


def test_forecast_jobs_list_filters_by_status() -> None:
    response = client.get("/api/v1/forecast/jobs", params={"status": "failed"})

    assert response.status_code == 200
    assert response.json()["jobs"] == []


def test_forecast_job_retry_contract() -> None:
    response = client.post(
        "/api/v1/forecast/jobs",
        json={"latitude": 37.5665, "longitude": 126.9780},
    )
    created = response.json()
    completed = client.get(created["links"]["self"]).json()

    retry_response = client.post(completed["links"]["retry"])

    assert retry_response.status_code == 202
    retry = retry_response.json()
    assert retry["parent_job_id"] == completed["id"]
    assert retry["attempt"] == completed["attempt"] + 1
    assert retry["status"] == "queued"
    assert retry["latitude"] == completed["latitude"]
    assert retry["longitude"] == completed["longitude"]


def test_forecast_job_cancel_rejects_completed_job() -> None:
    response = client.post(
        "/api/v1/forecast/jobs",
        json={"latitude": 37.5665, "longitude": 126.9780},
    )
    completed = client.get(response.json()["links"]["self"]).json()

    cancel_response = client.post(completed["links"]["cancel"])

    assert cancel_response.status_code == 409
    assert "Cannot cancel a succeeded forecast job" in cancel_response.json()["detail"]


def test_forecast_job_cleanup_contract() -> None:
    response = client.post(
        "/api/v1/forecast/jobs/cleanup",
        json={"older_than_hours": 8760, "statuses": ["succeeded", "failed", "cancelled"]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["deleted_count"] == 0
    assert body["statuses"] == ["cancelled", "failed", "succeeded"]


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
